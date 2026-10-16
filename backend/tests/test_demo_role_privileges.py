"""public_demo startup privilege verification (verify_demo_role_privileges).

Almost every test uses a fake connection that answers each catalog query
with canned rows, so nothing reaches a database and no LOGIN role is needed.
Unknown SQL makes the fake fail, so the check cannot silently run anything
it does not declare.

The one real-database test runs the same queries on careerpilot_test as the
existing NOLOGIN careerpilot_test_reader (via SET LOCAL ROLE, in the test
only). It proves the SQL is valid on PostgreSQL 16 and that a SELECT-only
role fails exactly one check: the SET ROLE detection.
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

import backend.app.database as database
import backend.app.main as main_module
from backend.app.database import (
    DEMO_COLUMN_GRANTS_QUERY,
    DEMO_DATABASE_QUERY,
    DEMO_FORBIDDEN_ROLE_ATTRIBUTES,
    DEMO_FORBIDDEN_SEQUENCE_PRIVILEGES,
    DEMO_FORBIDDEN_TABLE_PRIVILEGES,
    DEMO_MEMBERSHIPS_QUERY,
    DEMO_OWNED_QUERY,
    DEMO_OWNERSHIP_COUNT_QUERY,
    DEMO_ROLE_QUERY,
    DEMO_SCHEMA_CREATE_QUERY,
    DEMO_SCHEMA_USAGE_QUERY,
    DEMO_SEQUENCE_QUERY,
    DEMO_SEQUENCES_QUERY,
    DEMO_TABLE_QUERY,
    DEMO_WRITABLE_RELATIONS_QUERY,
    DemoPrivilegeError,
    demo_privilege_problems,
    verify_demo_role_privileges,
)
from backend.tests.db_safety import require_test_database


DEMO_USER = "demo_login_placeholder"
DEMO_PASSWORD = "demo-placeholder-secret"
DEMO_HOST = "demo-db.invalid"
DEMO_URL = f"postgresql://{DEMO_USER}:{DEMO_PASSWORD}@{DEMO_HOST}:5432/careerpilot_demo"

MODE_VARS = [
    "CAREERPILOT_MODE",
    "RENDER",
    "CAREERPILOT_DEMO_DATABASE_URL",
    "DATABASE_URL",
    "CAREERPILOT_ADMIN_DATABASE_URL",
]

SEQUENCE_OID = 16390
SET_ROLE_PROBLEM = "session_user differs from current_user (SET ROLE in effect)"


def good_responses():
    """Catalog answers for a strictly SELECT-only role."""
    return {
        DEMO_ROLE_QUERY: [{
            "same_role": True,
            **{column: False for column in DEMO_FORBIDDEN_ROLE_ATTRIBUTES},
        }],
        DEMO_MEMBERSHIPS_QUERY: [],
        DEMO_OWNED_QUERY: [],
        DEMO_OWNERSHIP_COUNT_QUERY: [{"owned": 0}],
        DEMO_DATABASE_QUERY: [{"can_create": False, "can_temp": False}],
        DEMO_SCHEMA_CREATE_QUERY: [],
        DEMO_SCHEMA_USAGE_QUERY: [{"can_use": True}],
        DEMO_TABLE_QUERY: [{
            "can_select": True,
            **{column: False for column in DEMO_FORBIDDEN_TABLE_PRIVILEGES},
        }],
        DEMO_WRITABLE_RELATIONS_QUERY: [],
        DEMO_COLUMN_GRANTS_QUERY: [],
        DEMO_SEQUENCES_QUERY: [
            {"oid": SEQUENCE_OID, "name": "job_applications_id_seq"}
        ],
        DEMO_SEQUENCE_QUERY: [
            {column: False for column in DEMO_FORBIDDEN_SEQUENCE_PRIVILEGES}
        ],
    }


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self, responses):
        self.responses = responses
        self.executed = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, dict(params or {})))
        if sql not in self.responses:
            raise AssertionError(f"Unexpected SQL: {sql}")
        return FakeResult(self.responses[sql])


class FakeEngine:
    def __init__(self, responses, failures=0):
        self.connection = FakeConnection(responses)
        self.failures = failures
        self.attempts = 0

    @contextmanager
    def connect(self):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise OperationalError("connect", {}, Exception("not ready"))
        yield self.connection


def problems_with(**overrides):
    responses = good_responses()
    responses.update(overrides)
    return demo_privilege_problems(FakeConnection(responses))


def with_row(query, **values):
    """The good row for ``query`` with some values replaced."""
    row = dict(good_responses()[query][0])
    row.update(values)
    return {query: [row]}


def assert_rejected(overrides, expected):
    problems = problems_with(**overrides)
    assert any(expected in problem for problem in problems), problems
    with pytest.raises(DemoPrivilegeError, match="not strictly SELECT-only"):
        verify_demo_role_privileges(
            bind=FakeEngine({**good_responses(), **overrides}),
            retries=1,
            delay_seconds=0,
        )


# --- the accepted case ------------------------------------------------------


def test_select_only_role_passes():
    engine = FakeEngine(good_responses())

    verify_demo_role_privileges(bind=engine, retries=1, delay_seconds=0)

    assert demo_privilege_problems(FakeConnection(good_responses())) == []


def test_check_runs_only_declared_read_only_queries():
    connection = FakeConnection(good_responses())

    demo_privilege_problems(connection)

    # The fake rejects any SQL it does not know, so this is the full list:
    # single SELECT statements, with no role switching or statement chaining.
    assert connection.executed
    for sql, _ in connection.executed:
        assert sql.startswith("SELECT "), sql
        assert ";" not in sql
        assert "SET ROLE" not in sql.upper() and "SET LOCAL" not in sql.upper()


def test_required_table_is_checked_by_schema_and_name():
    connection = FakeConnection(good_responses())

    demo_privilege_problems(connection)

    table_calls = [p for sql, p in connection.executed if sql == DEMO_TABLE_QUERY]
    assert table_calls == [{"schema": "public", "name": "job_applications"}]


# --- identity and role attributes ------------------------------------------


def test_rejects_set_role_session():
    assert_rejected(with_row(DEMO_ROLE_QUERY, same_role=False), "SET ROLE")


@pytest.mark.parametrize("column, label", DEMO_FORBIDDEN_ROLE_ATTRIBUTES.items())
def test_rejects_forbidden_role_attribute(column, label):
    assert_rejected(with_row(DEMO_ROLE_QUERY, **{column: True}), f"role has {label}")


@pytest.mark.parametrize("column", DEMO_FORBIDDEN_ROLE_ATTRIBUTES)
def test_unknown_role_attribute_fails_closed(column):
    assert_rejected(with_row(DEMO_ROLE_QUERY, **{column: None}), "role has")


def test_rejects_unreadable_role_attributes():
    assert_rejected({DEMO_ROLE_QUERY: []}, "could not be read")


def test_rejects_role_memberships():
    assert_rejected(
        {DEMO_MEMBERSHIPS_QUERY: [{"name": "pg_write_all_data"}]},
        "member of: pg_write_all_data",
    )


# --- ownership --------------------------------------------------------------


@pytest.mark.parametrize(
    "owned",
    ["database (current)", "schema public", "relation public.job_applications"],
)
def test_rejects_owned_objects(owned):
    assert_rejected({DEMO_OWNED_QUERY: [{"name": owned}]}, f"role owns: {owned}")


def test_rejects_ownership_anywhere_in_cluster():
    assert_rejected({DEMO_OWNERSHIP_COUNT_QUERY: [{"owned": 2}]}, "owns 2 object(s)")


# --- database and schema ----------------------------------------------------


@pytest.mark.parametrize("value", [True, None])
def test_rejects_database_create(value):
    assert_rejected(
        with_row(DEMO_DATABASE_QUERY, can_create=value), "CREATE on the database"
    )


@pytest.mark.parametrize("value", [True, None])
def test_rejects_database_temporary(value):
    assert_rejected(
        with_row(DEMO_DATABASE_QUERY, can_temp=value), "TEMPORARY on the database"
    )


def test_rejects_schema_create():
    assert_rejected(
        {DEMO_SCHEMA_CREATE_QUERY: [{"name": "public"}]}, "CREATE on schema: public"
    )


@pytest.mark.parametrize("value", [False, None])
def test_rejects_missing_schema_usage(value):
    assert_rejected(
        with_row(DEMO_SCHEMA_USAGE_QUERY, can_use=value), "no USAGE on schema public"
    )


# --- tables -----------------------------------------------------------------


@pytest.mark.parametrize("value", [False, None])
def test_rejects_missing_select(value):
    assert_rejected(
        with_row(DEMO_TABLE_QUERY, can_select=value),
        "no SELECT on public.job_applications",
    )


@pytest.mark.parametrize("column, label", DEMO_FORBIDDEN_TABLE_PRIVILEGES.items())
def test_rejects_table_and_column_write_privileges(column, label):
    assert_rejected(
        with_row(DEMO_TABLE_QUERY, **{column: True}),
        f"{label} on public.job_applications",
    )


@pytest.mark.parametrize("column", DEMO_FORBIDDEN_TABLE_PRIVILEGES)
def test_unknown_table_privilege_fails_closed(column):
    assert_rejected(
        with_row(DEMO_TABLE_QUERY, **{column: None}), "on public.job_applications"
    )


def test_rejects_write_privilege_on_any_relation():
    assert_rejected(
        {DEMO_WRITABLE_RELATIONS_QUERY: [{"name": "other_schema.audit"}]},
        "write privilege or grant option on: other_schema.audit",
    )


def test_long_name_lists_are_truncated():
    names = [{"name": f"relation public.t{i:02d}"} for i in range(13)]

    problems = problems_with(**{DEMO_OWNED_QUERY: names})

    assert problems == [
        "role owns: " + ", ".join(n["name"] for n in names[:10]) + " (+3 more)"
    ]


def test_pg_settings_update_is_the_only_exemption():
    """PUBLIC's default UPDATE on pg_settings equals SET; nothing else is
    exempted, and pg_settings is still checked for every other privilege."""
    query = DEMO_WRITABLE_RELATIONS_QUERY
    assert query.count("pg_settings") == 1
    exempt, normal = query.split("THEN", 1)[1].split("ELSE", 1)
    assert "UPDATE" not in exempt and "INSERT" in exempt and "DELETE" in exempt
    assert "UPDATE" in normal


def test_column_grants_exempt_only_pg_settings_update():
    query = DEMO_COLUMN_GRANTS_QUERY

    assert "a.attrelid <> 'pg_catalog.pg_settings'::regclass" in query
    assert "has_column_privilege(a.attrelid, a.attnum, 'UPDATE')" in query
    assert "has_column_privilege(a.attrelid, a.attnum, 'INSERT')" in query
    assert "has_column_privilege(a.attrelid, a.attnum, 'REFERENCES')" in query
    assert "SELECT WITH GRANT OPTION" in query


def test_rejects_column_level_grants_on_any_relation():
    assert_rejected(
        {DEMO_COLUMN_GRANTS_QUERY: [{"name": "job_applications"}]},
        "column-level write privilege or grant option on: job_applications",
    )


# --- sequences --------------------------------------------------------------


@pytest.mark.parametrize("column, label", DEMO_FORBIDDEN_SEQUENCE_PRIVILEGES.items())
def test_rejects_sequence_privileges(column, label):
    assert_rejected(
        with_row(DEMO_SEQUENCE_QUERY, **{column: True}),
        f"{label} on sequence job_applications_id_seq",
    )


def test_unknown_sequence_privilege_fails_closed():
    assert_rejected(
        with_row(DEMO_SEQUENCE_QUERY, can_usage=None), "on sequence"
    )


def test_sequences_are_listed_before_privilege_functions_run():
    """Guards the WHERE evaluation-order bug seen in Step 73C-7."""
    assert "has_sequence_privilege" not in DEMO_SEQUENCES_QUERY
    connection = FakeConnection(good_responses())

    demo_privilege_problems(connection)

    sqls = [sql for sql, _ in connection.executed]
    listing = sqls.index(DEMO_SEQUENCES_QUERY)
    checks = [i for i, sql in enumerate(sqls) if sql == DEMO_SEQUENCE_QUERY]
    assert checks and all(i > listing for i in checks)
    assert [p for sql, p in connection.executed if sql == DEMO_SEQUENCE_QUERY] == [
        {"oid": SEQUENCE_OID}
    ]


def test_no_sequences_means_no_sequence_privilege_calls():
    connection = FakeConnection({**good_responses(), DEMO_SEQUENCES_QUERY: []})

    assert demo_privilege_problems(connection) == []
    assert all(sql != DEMO_SEQUENCE_QUERY for sql, _ in connection.executed)


# --- reporting and connection handling --------------------------------------


def test_reports_every_problem_at_once():
    overrides = {
        **with_row(DEMO_ROLE_QUERY, rolsuper=True),
        **with_row(DEMO_DATABASE_QUERY, can_temp=True),
        **with_row(DEMO_TABLE_QUERY, can_insert=True),
    }

    problems = problems_with(**overrides)

    assert len(problems) == 3


def test_retries_connection_errors():
    engine = FakeEngine(good_responses(), failures=2)

    verify_demo_role_privileges(bind=engine, retries=5, delay_seconds=0)

    assert engine.attempts == 3


def test_reraises_after_retries():
    engine = FakeEngine(good_responses(), failures=5)

    with pytest.raises(OperationalError):
        verify_demo_role_privileges(bind=engine, retries=2, delay_seconds=0)


@pytest.fixture
def public_demo_env(monkeypatch):
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CAREERPILOT_MODE", "public_demo")
    monkeypatch.setenv("CAREERPILOT_DEMO_DATABASE_URL", DEMO_URL)
    database.reset_engine()
    yield monkeypatch
    database.reset_engine()


def test_uses_configured_engine_and_never_leaks_url(public_demo_env, monkeypatch):
    bad = FakeEngine({
        **good_responses(),
        **with_row(DEMO_ROLE_QUERY, rolsuper=True, same_role=False),
        DEMO_OWNED_QUERY: [{"name": "database (current)"}],
    })
    used = []

    def fake_get_engine():
        used.append(True)
        return bad

    monkeypatch.setattr(database, "get_engine", fake_get_engine)

    with pytest.raises(DemoPrivilegeError) as excinfo:
        verify_demo_role_privileges(retries=1, delay_seconds=0)

    assert used == [True]
    message = str(excinfo.value)
    for secret in (DEMO_PASSWORD, DEMO_USER, DEMO_HOST, "careerpilot_demo", DEMO_URL):
        assert secret not in message


def test_public_demo_engine_pool_is_small(public_demo_env):
    engine = database.get_engine()

    assert engine.pool.size() == database.PUBLIC_DEMO_POOL_SIZE == 2
    assert engine.pool._max_overflow == database.PUBLIC_DEMO_MAX_OVERFLOW == 1
    assert engine.pool._recycle == database.PUBLIC_DEMO_POOL_RECYCLE_SECONDS
    assert engine.pool._timeout == database.PUBLIC_DEMO_POOL_TIMEOUT_SECONDS


# --- startup ----------------------------------------------------------------


@pytest.fixture
def restore_app_settings():
    """Restore app.state.settings so public_demo never leaks into later tests."""
    state = main_module.app.state
    previous = getattr(state, "settings", None)
    yield
    if previous is None:
        if hasattr(state, "settings"):
            del state.settings
    else:
        state.settings = previous


def test_public_demo_startup_verifies_privileges_after_schema(
    public_demo_env, monkeypatch, restore_app_settings
):
    ran = []
    monkeypatch.setattr(main_module, "init_db", lambda: ran.append("init_db"))
    monkeypatch.setattr(main_module, "verify_schema", lambda: ran.append("schema"))
    monkeypatch.setattr(
        main_module, "verify_demo_role_privileges", lambda: ran.append("privileges")
    )

    with TestClient(main_module.app) as client:
        assert client.get("/health").status_code == 200

    assert ran == ["schema", "privileges"]


def test_public_demo_startup_refused_when_role_not_select_only(
    public_demo_env, monkeypatch, restore_app_settings
):
    monkeypatch.setattr(main_module, "verify_schema", lambda: None)
    bad = FakeEngine({**good_responses(), **with_row(DEMO_TABLE_QUERY, can_update=True)})
    monkeypatch.setattr(database, "get_engine", lambda: bad)

    with pytest.raises(DemoPrivilegeError, match="UPDATE on public.job_applications"):
        with TestClient(main_module.app):
            pass


def test_local_startup_does_not_run_privilege_check(monkeypatch, restore_app_settings):
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)
    ran = []
    monkeypatch.setattr(main_module, "init_db", lambda: ran.append("init_db"))
    monkeypatch.setattr(
        main_module, "verify_demo_role_privileges", lambda: ran.append("privileges")
    )

    with TestClient(main_module.app):
        pass

    assert ran == ["init_db"]


# --- real SQL on careerpilot_test -------------------------------------------


def test_queries_run_on_postgres_as_select_only_reader(test_db_engine):
    """Validates the SQL on PostgreSQL 16 using the NOLOGIN test reader.

    SET LOCAL ROLE is used by this test only, never by the startup check, so
    the check correctly reports exactly the SET ROLE problem and nothing
    else. Always rolled back; NullPool closes the connection.
    """
    engine = create_engine(test_db_engine.url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                require_test_database(connection)
                connection.execute(text("SET LOCAL ROLE careerpilot_test_reader"))

                problems = demo_privilege_problems(connection)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    assert problems == [SET_ROLE_PROBLEM]


def test_queries_reject_the_owner_on_postgres(test_db_engine):
    """The test (owner, superuser) credentials must fail the check."""
    with test_db_engine.connect() as connection:
        require_test_database(connection)
        problems = demo_privilege_problems(connection)
        connection.rollback()

    joined = "; ".join(problems)
    assert "role has SUPERUSER" in joined
    assert "database (current)" in joined
    assert "careerpilot_test" not in joined
    assert any(
        p.endswith(" on public.job_applications") and "INSERT" in p
        for p in problems
    )
    # Long lists are truncated so the message stays readable.
    assert "more)" in joined
