"""Mode-aware, lazy engine selection in database.py.

Every URL here is a placeholder on the never-resolving ``.invalid`` domain.
Creating an engine does not connect, and no test checks out a connection, so
nothing here reaches any database -- local, test, or external.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

import backend.app.database as database
import backend.app.main as main_module
from backend.app.settings import SettingsError


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEMO_PASSWORD = "demo-placeholder-secret"
DEMO_URL = (
    f"postgresql://demo_reader:{DEMO_PASSWORD}"
    "@demo-db.invalid:5432/careerpilot_demo"
)

# Stand-ins for local owner credentials: public_demo must never use them.
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


@pytest.fixture
def clean_env(monkeypatch):
    """Clear mode variables and install placeholder POSTGRES_* values."""
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


def assert_no_owner_credentials(url: URL):
    rendered = url.render_as_string(hide_password=False)
    for value in OWNER_ENV.values():
        assert value not in rendered


# --- no engine at import ----------------------------------------------------


def test_importing_app_creates_no_engine_in_public_demo():
    """Import the app in a fresh interpreter with create_engine booby-trapped."""
    script = (
        "import sqlalchemy\n"
        "def boom(*args, **kwargs):\n"
        "    raise SystemExit('create_engine called at import')\n"
        "sqlalchemy.create_engine = boom\n"
        "import backend.app.main\n"
        "import backend.app.database as database\n"
        "assert database._engine is None\n"
    )
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in MODE_VARS
    }
    env.update(
        {
            "CAREERPILOT_MODE": "public_demo",
            "CAREERPILOT_DEMO_DATABASE_URL": DEMO_URL,
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr[-2000:]


def test_no_engine_cached_before_first_use(clean_env):
    assert database._engine is None


# --- public_demo selection --------------------------------------------------


def test_public_demo_uses_only_demo_database_url(public_demo_env):
    url = database.get_engine().url

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "demo_reader"
    assert url.password == DEMO_PASSWORD
    assert url.host == "demo-db.invalid"
    assert url.port == 5432
    assert url.database == "careerpilot_demo"
    assert_no_owner_credentials(url)


def test_public_demo_accepts_explicit_psycopg_scheme(public_demo_env):
    public_demo_env.setenv(
        "CAREERPILOT_DEMO_DATABASE_URL",
        DEMO_URL.replace("postgresql://", "postgresql+psycopg://"),
    )

    url = database.get_engine().url

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "demo-db.invalid"


def test_public_demo_preserves_query_options(public_demo_env):
    public_demo_env.setenv(
        "CAREERPILOT_DEMO_DATABASE_URL", f"{DEMO_URL}?sslmode=require"
    )

    assert database.get_engine().url.query == {"sslmode": "require"}


def test_public_demo_session_is_bound_to_demo_engine(public_demo_env):
    generator = database.get_db()
    session = next(generator)
    try:
        assert isinstance(session, Session)
        assert session.get_bind() is database.get_engine()
        assert session.get_bind().url.host == "demo-db.invalid"
    finally:
        generator.close()


def test_public_demo_works_without_postgres_vars(public_demo_env):
    for name in OWNER_ENV:
        public_demo_env.delenv(name)

    assert database.get_engine().url.host == "demo-db.invalid"


# --- public_demo fails closed -----------------------------------------------


@pytest.fixture
def create_engine_must_not_run(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("create_engine ran despite an invalid configuration")

    monkeypatch.setattr(database, "create_engine", fail)


def test_public_demo_missing_url_does_not_fall_back(
    public_demo_env, create_engine_must_not_run
):
    public_demo_env.delenv("CAREERPILOT_DEMO_DATABASE_URL")

    with pytest.raises(SettingsError, match="CAREERPILOT_DEMO_DATABASE_URL"):
        database.get_engine()
    with pytest.raises(SettingsError):
        next(database.get_db())

    assert database._engine is None


def test_public_demo_with_forbidden_admin_url_does_not_fall_back(
    public_demo_env, create_engine_must_not_run
):
    public_demo_env.setenv("DATABASE_URL", "postgresql://owner@owner-db.invalid/db")

    with pytest.raises(SettingsError, match="DATABASE_URL"):
        database.get_engine()

    assert database._engine is None


@pytest.mark.parametrize(
    "bad_url",
    [
        f"not a url {DEMO_PASSWORD}",
        f"sqlite:///{DEMO_PASSWORD}.db",
        f"mysql://demo_reader:{DEMO_PASSWORD}@demo-db.invalid/careerpilot_demo",
        f"postgresql+asyncpg://demo_reader:{DEMO_PASSWORD}@demo-db.invalid/db",
        f"postgresql://:{DEMO_PASSWORD}@demo-db.invalid/careerpilot_demo",
        f"postgresql://demo_reader:{DEMO_PASSWORD}@/careerpilot_demo",
        f"postgresql://demo_reader:{DEMO_PASSWORD}@demo-db.invalid",
        f"postgresql://demo_reader:{DEMO_PASSWORD}@demo-db.invalid:port/db",
    ],
)
def test_public_demo_invalid_url_fails_closed_without_leaking(
    public_demo_env, create_engine_must_not_run, bad_url
):
    public_demo_env.setenv("CAREERPILOT_DEMO_DATABASE_URL", bad_url)

    with pytest.raises(SettingsError) as excinfo:
        database.get_engine()

    message = str(excinfo.value)
    assert "CAREERPILOT_DEMO_DATABASE_URL" in message
    assert DEMO_PASSWORD not in message
    assert bad_url not in message
    # The parser's own error (which can quote the URL) is not chained.
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ or excinfo.value.__context__ is None
    assert database._engine is None


def test_switching_to_public_demo_replaces_local_engine(clean_env):
    local_engine = database.get_engine()
    assert local_engine.url.host == "owner-db.invalid"

    clean_env.setenv("CAREERPILOT_MODE", "public_demo")
    clean_env.setenv("CAREERPILOT_DEMO_DATABASE_URL", DEMO_URL)

    demo_engine = database.get_engine()
    assert demo_engine is not local_engine
    assert_no_owner_credentials(demo_engine.url)


def test_switching_to_broken_public_demo_does_not_reuse_local_engine(clean_env):
    database.get_engine()

    clean_env.setenv("CAREERPILOT_MODE", "public_demo")

    with pytest.raises(SettingsError):
        database.get_engine()
    with pytest.raises(SettingsError):
        database.get_session_factory()


def test_startup_refused_for_invalid_demo_url(public_demo_env):
    """The lifespan fails in verify_schema's engine lookup, before connecting."""
    public_demo_env.setenv("CAREERPILOT_DEMO_DATABASE_URL", "sqlite:///demo.db")
    state = main_module.app.state
    previous = getattr(state, "settings", None)

    try:
        with pytest.raises(SettingsError, match="CAREERPILOT_DEMO_DATABASE_URL"):
            with TestClient(main_module.app):
                pass
    finally:
        # The lifespan stores public_demo settings on app.state before
        # init_db fails; restore them so later tests are not made read-only.
        if previous is None:
            if hasattr(state, "settings"):
                del state.settings
        else:
            state.settings = previous

    assert database._engine is None


# --- local mode unchanged ---------------------------------------------------


def test_local_mode_uses_postgres_vars(clean_env):
    engine = database.get_engine()

    assert engine.url == URL.create(
        drivername="postgresql+psycopg",
        username="owner_placeholder",
        password="owner-placeholder-secret",
        host="owner-db.invalid",
        port=6543,
        database="careerpilot_owner",
    )


def test_local_mode_host_and_port_defaults(clean_env):
    clean_env.delenv("POSTGRES_HOST")
    clean_env.delenv("POSTGRES_PORT")

    url = database.get_engine().url

    assert url.host == "127.0.0.1"
    assert url.port == 5432


def test_local_mode_ignores_demo_database_url(clean_env):
    clean_env.setenv("CAREERPILOT_DEMO_DATABASE_URL", DEMO_URL)

    assert database.get_engine().url.host == "owner-db.invalid"


def test_local_mode_engine_and_sessions_are_reused(clean_env):
    engine = database.get_engine()
    factory = database.get_session_factory()

    assert database.get_engine() is engine
    assert database.get_session_factory() is factory
    assert factory.kw["bind"] is engine
    assert factory.kw["autoflush"] is False
    assert engine.pool._pre_ping is True


def test_local_mode_session_settings(clean_env):
    generator = database.get_db()
    session = next(generator)
    try:
        assert session.get_bind() is database.get_engine()
        assert session.autoflush is False
    finally:
        generator.close()


@pytest.mark.parametrize("missing", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"])
def test_local_mode_missing_postgres_var_fails_without_leaking(clean_env, missing):
    clean_env.delenv(missing)

    with pytest.raises(SettingsError, match=missing) as excinfo:
        database.get_engine()

    assert "owner-placeholder-secret" not in str(excinfo.value)
