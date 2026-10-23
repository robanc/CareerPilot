"""public_demo read-only sessions, schema verification, and startup.

Every URL is a placeholder on the never-resolving ``.invalid`` domain. The
DBAPI connect call, connections, and the schema inspector are all mocked, so
nothing here reaches any database -- local, test, or external.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import InternalError, OperationalError

import backend.app.database as database
import backend.app.main as main_module
from backend.app.database import (
    PUBLIC_DEMO_STATEMENT_TIMEOUT_MS,
    ReadOnlySessionError,
    SchemaError,
    verify_read_only_session,
)
from backend.app.settings import SettingsError
from backend.tests.db_safety import require_test_database


DEMO_PASSWORD = "demo-placeholder-secret"
DEMO_URL = (
    f"postgresql://demo_reader:{DEMO_PASSWORD}"
    "@demo-db.invalid:5432/careerpilot_demo"
)

OWNER_ENV = {
    "POSTGRES_USER": "owner_placeholder",
    "POSTGRES_PASSWORD": "owner-placeholder-secret",
    "POSTGRES_HOST": "owner-db.invalid",
    "POSTGRES_PORT": "6543",
    "POSTGRES_DB": "careerpilot_owner",
}

MODE_VARS = [
    "CAREERPILOT_MODE",
    "RENDER",
    "CAREERPILOT_DEMO_DATABASE_URL",
    "DATABASE_URL",
    "CAREERPILOT_ADMIN_DATABASE_URL",
]

READ_ONLY_OPTION = "-c default_transaction_read_only=on"
TIMEOUT_OPTION = f"-c statement_timeout={PUBLIC_DEMO_STATEMENT_TIMEOUT_MS}"
GOOD_SETTINGS = [
    ("default_transaction_read_only", "on"),
    ("statement_timeout", str(PUBLIC_DEMO_STATEMENT_TIMEOUT_MS)),
]


@pytest.fixture
def clean_env(monkeypatch):
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in OWNER_ENV.items():
        monkeypatch.setenv(name, value)
    database.reset_engine()
    yield monkeypatch
    database.reset_engine()


@pytest.fixture
def public_demo_env(clean_env):
    clean_env.setenv("CAREERPILOT_MODE", "public_demo")
    clean_env.setenv("CAREERPILOT_DEMO_DATABASE_URL", DEMO_URL)
    return clean_env


class ConnectAttempted(Exception):
    pass


def captured_connect_params(engine, monkeypatch) -> dict:
    """Return the kwargs the engine would pass to psycopg.connect.

    The dialect's connect is replaced, so no connection is ever opened.
    """
    captured = {}

    def fake_connect(*args, **kwargs):
        captured.update(kwargs)
        raise ConnectAttempted

    monkeypatch.setattr(engine.dialect, "connect", fake_connect)
    with pytest.raises(ConnectAttempted):
        engine.connect()
    return captured


@pytest.fixture
def create_all_must_not_run(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("create_all ran in public_demo")

    monkeypatch.setattr(database.Base.metadata, "create_all", fail)


class FakeInspector:
    def __init__(self, existing):
        self.existing = set(existing)

    def has_table(self, name):
        return name in self.existing


def install_inspector(monkeypatch, existing=("job_applications", "resumes")):
    calls = []

    def fake_inspect(target):
        calls.append(target)
        return FakeInspector(existing)

    monkeypatch.setattr(database, "inspect", fake_inspect)
    return calls


# --- public_demo engine session settings ------------------------------------


def test_public_demo_engine_sends_read_only_and_timeout_options(
    public_demo_env, monkeypatch
):
    params = captured_connect_params(database.get_engine(), monkeypatch)

    assert READ_ONLY_OPTION in params["options"]
    assert TIMEOUT_OPTION in params["options"]


def test_public_demo_statement_timeout_is_short():
    assert 0 < PUBLIC_DEMO_STATEMENT_TIMEOUT_MS <= 10_000


def test_demo_url_options_cannot_disable_read_only(public_demo_env, monkeypatch):
    public_demo_env.setenv(
        "CAREERPILOT_DEMO_DATABASE_URL",
        f"{DEMO_URL}?options=-c%20default_transaction_read_only%3Doff",
    )

    params = captured_connect_params(database.get_engine(), monkeypatch)

    assert READ_ONLY_OPTION in params["options"]
    assert "=off" not in params["options"]


def test_public_demo_keeps_other_url_query_options(public_demo_env, monkeypatch):
    public_demo_env.setenv(
        "CAREERPILOT_DEMO_DATABASE_URL", f"{DEMO_URL}?sslmode=require"
    )

    params = captured_connect_params(database.get_engine(), monkeypatch)

    assert params["sslmode"] == "require"
    assert READ_ONLY_OPTION in params["options"]


def test_public_demo_engine_verifies_each_connection(public_demo_env):
    engine = database.get_engine()

    assert event.contains(engine, "connect", verify_read_only_session)
    assert engine.pool._pre_ping is True


# --- local mode unchanged ---------------------------------------------------


def test_local_engine_sends_no_session_options(clean_env, monkeypatch):
    engine = database.get_engine()
    params = captured_connect_params(engine, monkeypatch)

    assert "options" not in params
    assert params["host"] == "owner-db.invalid"
    assert params["dbname"] == "careerpilot_owner"
    assert not event.contains(engine, "connect", verify_read_only_session)
    assert engine.pool._pre_ping is True


def test_local_mode_ignores_demo_url_options(clean_env, monkeypatch):
    clean_env.setenv("CAREERPILOT_DEMO_DATABASE_URL", DEMO_URL)

    params = captured_connect_params(database.get_engine(), monkeypatch)

    assert "options" not in params


# --- connect-time verification ----------------------------------------------


class FakeCursor:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error
        self.executed = []
        self.closed = False

    def execute(self, sql):
        self.executed.append(sql)
        if self.error is not None:
            raise self.error

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True


class FakeDBAPIConnection:
    def __init__(self, rows, error=None):
        self.cursor_obj = FakeCursor(rows, error)
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_verify_accepts_read_only_session():
    connection = FakeDBAPIConnection(GOOD_SETTINGS)

    verify_read_only_session(connection, None)

    assert "pg_settings" in connection.cursor_obj.executed[0]
    assert connection.cursor_obj.closed
    assert connection.rolled_back
    assert not connection.closed


@pytest.mark.parametrize(
    "rows, wrong",
    [
        (
            [("default_transaction_read_only", "off"), GOOD_SETTINGS[1]],
            "default_transaction_read_only",
        ),
        ([GOOD_SETTINGS[1]], "default_transaction_read_only"),
        ([GOOD_SETTINGS[0], ("statement_timeout", "0")], "statement_timeout"),
        ([GOOD_SETTINGS[0]], "statement_timeout"),
        ([], "default_transaction_read_only, statement_timeout"),
    ],
    ids=["read-only-off", "read-only-missing", "no-timeout",
         "timeout-missing", "nothing-applied"],
)
def test_verify_rejects_and_closes_unsafe_session(rows, wrong):
    connection = FakeDBAPIConnection(rows)

    with pytest.raises(ReadOnlySessionError) as excinfo:
        verify_read_only_session(connection, None)

    assert wrong in str(excinfo.value)
    assert connection.closed


def test_verify_closes_connection_when_check_fails():
    connection = FakeDBAPIConnection([], error=RuntimeError("query failed"))

    with pytest.raises(RuntimeError, match="query failed"):
        verify_read_only_session(connection, None)

    assert connection.cursor_obj.closed
    assert connection.closed


# --- verify_schema ----------------------------------------------------------


def test_verify_schema_passes_when_tables_exist(
    public_demo_env, monkeypatch, create_all_must_not_run
):
    calls = install_inspector(monkeypatch)

    database.verify_schema()

    assert calls == [database.get_engine()]


def test_verify_schema_fails_closed_on_missing_table(
    public_demo_env, monkeypatch, create_all_must_not_run
):
    calls = install_inspector(monkeypatch, existing=())

    with pytest.raises(SchemaError) as excinfo:
        database.verify_schema(delay_seconds=0)

    message = str(excinfo.value)
    assert "job_applications" in message
    assert DEMO_PASSWORD not in message
    assert "demo-db.invalid" not in message
    # A missing table is not a transient error, so it is not retried.
    assert len(calls) == 1


def test_verify_schema_retries_connection_errors(public_demo_env, monkeypatch):
    attempts = []

    def flaky_inspect(target):
        attempts.append(target)
        if len(attempts) < 3:
            raise OperationalError("SELECT 1", {}, Exception("not ready"))
        return FakeInspector({"job_applications", "resumes"})

    monkeypatch.setattr(database, "inspect", flaky_inspect)

    database.verify_schema(retries=5, delay_seconds=0)

    assert len(attempts) == 3


def test_verify_schema_reraises_after_retries(public_demo_env, monkeypatch):
    def down(target):
        raise OperationalError("SELECT 1", {}, Exception("down"))

    monkeypatch.setattr(database, "inspect", down)

    with pytest.raises(OperationalError):
        database.verify_schema(retries=2, delay_seconds=0)


# --- init_db never creates tables in public_demo ------------------------------


def test_init_db_refuses_in_public_demo(public_demo_env, create_all_must_not_run):
    with pytest.raises(SettingsError, match="create_all"):
        database.init_db(retries=1, delay_seconds=0)


def test_init_db_refuses_in_public_demo_even_with_bind(
    public_demo_env, create_all_must_not_run
):
    with pytest.raises(SettingsError, match="create_all"):
        database.init_db(bind=object(), retries=1, delay_seconds=0)


def test_init_db_still_creates_tables_in_local_mode(clean_env, monkeypatch):
    binds = []
    monkeypatch.setattr(
        database.Base.metadata, "create_all", lambda bind: binds.append(bind)
    )
    sentinel = object()

    database.init_db(bind=sentinel, retries=1, delay_seconds=0)

    assert binds == [sentinel]


# --- startup ----------------------------------------------------------------


@pytest.fixture
def restore_app_settings():
    """The lifespan stores settings on app.state; restore them afterwards
    so public_demo settings never make later tests read-only."""
    state = main_module.app.state
    previous = getattr(state, "settings", None)
    yield
    if previous is None:
        if hasattr(state, "settings"):
            del state.settings
    else:
        state.settings = previous


def test_public_demo_startup_verifies_schema_without_create_all(
    public_demo_env, monkeypatch, create_all_must_not_run, restore_app_settings
):
    calls = install_inspector(monkeypatch)
    # The privilege check is covered in test_demo_role_privileges.py.
    monkeypatch.setattr(main_module, "verify_demo_role_privileges", lambda: None)

    with TestClient(main_module.app) as client:
        assert client.get("/health").status_code == 200

    assert len(calls) == 1


def test_public_demo_startup_refused_when_table_missing(
    public_demo_env, monkeypatch, create_all_must_not_run, restore_app_settings
):
    install_inspector(monkeypatch, existing=())

    with pytest.raises(SchemaError, match="job_applications"):
        with TestClient(main_module.app):
            pass


def test_read_only_session_rejects_writes_on_test_database(test_db_engine):
    """The one real-database test here: careerpilot_test only.

    Uses the test engine's (owner) credentials, so it proves the session
    settings are applied and enforced by PostgreSQL -- NOT that the demo
    role lacks privileges, which is still pending.
    """
    read_only_engine = database.create_read_only_engine(test_db_engine.url)
    try:
        with read_only_engine.connect() as connection:
            require_test_database(connection)
            assert connection.execute(
                text("SHOW transaction_read_only")
            ).scalar_one() == "on"
            assert connection.execute(
                text("SHOW statement_timeout")
            ).scalar_one() == "5s"
            connection.rollback()

            for statement in [
                "INSERT INTO job_applications (company_name, job_title, "
                "application_date, status, created_at, updated_at) VALUES "
                "('X', 'Y', '2026-10-16', 'Saved', now(), now())",
                "UPDATE job_applications SET notes = 'x'",
                "DELETE FROM job_applications",
                "CREATE TABLE readonly_probe (id int)",
                "CREATE TEMP TABLE readonly_probe (id int)",
            ]:
                with pytest.raises(InternalError, match="read-only transaction"):
                    connection.execute(text(statement))
                connection.rollback()
    finally:
        read_only_engine.dispose()


def test_local_startup_still_runs_init_db(clean_env, monkeypatch, restore_app_settings):
    ran = []
    monkeypatch.setattr(main_module, "init_db", lambda: ran.append("init_db"))
    monkeypatch.setattr(
        main_module, "verify_schema", lambda: ran.append("verify_schema")
    )

    with TestClient(main_module.app):
        pass

    assert ran == ["init_db"]
