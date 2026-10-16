"""Database engine and session configuration.

The engine is created lazily, on first use, from the operating mode in
settings.py -- never at module import -- so importing this module (or the
app) builds no engine and reads no database credentials.

- ``local``: connects with the POSTGRES_* variables (locally from ``.env``),
  exactly as before.
- ``public_demo``: connects only with Settings.demo_database_url
  (CAREERPILOT_DEMO_DATABASE_URL). POSTGRES_* are ignored even when set, and
  there is no fallback: a missing or invalid demo URL raises SettingsError.

public_demo connections are also session-level read-only: every connection
starts with default_transaction_read_only=on and a short statement_timeout,
and is checked on connect, failing closed if the server did not apply them.
public_demo startup never runs create_all; it only verifies the tables exist.

WARNING: read-only transactions are defense-in-depth, not a privilege
boundary -- a client can SET them off. The dedicated SELECT-only demo role is
NOT created or enforced yet, so public_demo is still NOT SAFE TO DEPLOY.
Error messages name variables but never include their values.
"""

import os
import threading
import time
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.settings import (
    DEMO_DATABASE_URL_ENV_VAR,
    Settings,
    SettingsError,
    load_settings,
)


# Project root: C:\Users\roban\CareerPilot
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load local database settings without overriding existing environment variables.
load_dotenv(PROJECT_ROOT / ".env")


DRIVERNAME = "postgresql+psycopg"
# Schemes accepted for the demo URL; all are normalized to DRIVERNAME.
# "postgresql://" is the form hosting providers usually supply.
DEMO_URL_DRIVERNAMES = ("postgresql", DRIVERNAME)
LOCAL_REQUIRED_ENV_VARS = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")

# public_demo session settings, sent as libpq startup options. They override
# any "options" query parameter in the demo URL, so the URL cannot turn
# read-only off.
PUBLIC_DEMO_STATEMENT_TIMEOUT_MS = 5000
PUBLIC_DEMO_CONNECT_OPTIONS = (
    "-c default_transaction_read_only=on "
    f"-c statement_timeout={PUBLIC_DEMO_STATEMENT_TIMEOUT_MS}"
)
# Expected pg_settings values (statement_timeout is in milliseconds there).
PUBLIC_DEMO_SESSION_SETTINGS = {
    "default_transaction_read_only": "on",
    "statement_timeout": str(PUBLIC_DEMO_STATEMENT_TIMEOUT_MS),
}
PUBLIC_DEMO_SETTINGS_QUERY = (
    "SELECT name, setting FROM pg_settings "
    "WHERE name IN ('default_transaction_read_only', 'statement_timeout')"
)


class ReadOnlySessionError(RuntimeError):
    """Raised when a public_demo connection is not read-only as required."""


class SchemaError(RuntimeError):
    """Raised when public_demo finds the database schema incomplete."""


def local_database_url(environ: Mapping[str, str] | None = None) -> URL:
    """Build the local-mode URL from POSTGRES_* (used only in local mode)."""
    if environ is None:
        environ = os.environ

    missing = [name for name in LOCAL_REQUIRED_ENV_VARS if name not in environ]
    if missing:
        raise SettingsError(
            f"Local database configuration is incomplete: "
            f"{', '.join(missing)} is not set."
        )

    return URL.create(
        drivername=DRIVERNAME,
        username=environ["POSTGRES_USER"],
        password=environ["POSTGRES_PASSWORD"],
        host=environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(environ.get("POSTGRES_PORT", "5432")),
        database=environ["POSTGRES_DB"],
    )


def public_demo_database_url(settings: Settings) -> URL:
    """Parse and validate the demo URL. Fails closed; never echoes the value."""
    raw_url = settings.demo_database_url
    if not raw_url:
        raise SettingsError(
            f"Refusing to connect: public_demo requires a non-empty "
            f"{DEMO_DATABASE_URL_ENV_VAR}."
        )

    try:
        url = make_url(raw_url)
    except (ArgumentError, ValueError):
        # "from None": the parser's own message can contain the raw URL.
        raise SettingsError(
            f"Refusing to connect: {DEMO_DATABASE_URL_ENV_VAR} is not a "
            f"valid database URL."
        ) from None

    if url.drivername not in DEMO_URL_DRIVERNAMES:
        raise SettingsError(
            f"Refusing to connect: {DEMO_DATABASE_URL_ENV_VAR} must use the "
            f"postgresql:// or {DRIVERNAME}:// scheme."
        )

    missing = [
        part
        for part, value in (
            ("username", url.username),
            ("host", url.host),
            ("database name", url.database),
        )
        if not value
    ]
    if missing:
        raise SettingsError(
            f"Refusing to connect: {DEMO_DATABASE_URL_ENV_VAR} is missing "
            f"its {', '.join(missing)}."
        )

    return url.set(drivername=DRIVERNAME)


def database_url_for(settings: Settings) -> URL:
    if settings.is_public_demo:
        return public_demo_database_url(settings)
    return local_database_url()


def verify_read_only_session(dbapi_connection, connection_record=None) -> None:
    """Connect hook: fail closed unless the session settings took effect.

    Guards against a server or pooler that silently ignores the startup
    options. On failure the connection is closed, never handed out.
    """
    try:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(PUBLIC_DEMO_SETTINGS_QUERY)
            actual = {name: setting for name, setting in cursor.fetchall()}
        finally:
            cursor.close()
        # End the implicit transaction the check opened.
        dbapi_connection.rollback()
    except Exception:
        dbapi_connection.close()
        raise

    wrong = [
        name
        for name, expected in PUBLIC_DEMO_SESSION_SETTINGS.items()
        if actual.get(name) != expected
    ]
    if wrong:
        dbapi_connection.close()
        raise ReadOnlySessionError(
            f"Refusing to use a public_demo connection: "
            f"{', '.join(wrong)} was not applied by the server."
        )


def create_read_only_engine(url: URL) -> Engine:
    """Create a public_demo engine whose every connection is read-only."""
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": PUBLIC_DEMO_CONNECT_OPTIONS},
    )
    event.listen(engine, "connect", verify_read_only_session)
    return engine


def create_engine_for(settings: Settings) -> Engine:
    """Create (but do not connect) the engine for the given mode."""
    url = database_url_for(settings)
    if settings.is_public_demo:
        return create_read_only_engine(url)
    return create_engine(url, pool_pre_ping=True)


_lock = threading.Lock()
_engine: Engine | None = None
_engine_settings: Settings | None = None
_session_factory: sessionmaker[Session] | None = None


def _current() -> tuple[Engine, sessionmaker[Session]]:
    """Return the engine and session factory for the current settings.

    Settings are re-read on every call, so the engine always matches the
    current mode; if the mode changes, the old engine is disposed and
    replaced rather than reused. A failure caches nothing.
    """
    global _engine, _engine_settings, _session_factory

    settings = load_settings()
    with _lock:
        if _engine is None or _engine_settings != settings:
            new_engine = create_engine_for(settings)
            if _engine is not None:
                _engine.dispose()
            _engine = new_engine
            _engine_settings = settings
            _session_factory = sessionmaker(
                bind=new_engine,
                autoflush=False,
                autocommit=False,
            )
        return _engine, _session_factory


def get_engine() -> Engine:
    """Return the engine for the current mode, creating it on first use."""
    return _current()[0]


def get_session_factory() -> sessionmaker[Session]:
    return _current()[1]


def reset_engine() -> None:
    """Dispose of and forget the cached engine (used by tests)."""
    global _engine, _engine_settings, _session_factory

    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _engine_settings = None
        _session_factory = None


class Base(DeclarativeBase):
    pass


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db(
    bind=None,
    retries: int = 5,
    delay_seconds: float = 1.0,
) -> None:
    """Create any missing tables. Never drops or alters existing ones.

    SQLAlchemy's create_all is conditional (checkfirst), so this is safe to
    run on every startup against a populated database: existing tables are
    detected and skipped, and the only DDL ever emitted is CREATE TABLE.

    This does NOT migrate existing tables. Adding or changing a model column
    will silently do nothing here -- adopt Alembic before the first schema
    change.

    The bounded retry covers the gap between PostgreSQL reporting ready via
    pg_isready and actually accepting connections. It re-raises once the
    attempts are exhausted so an unreachable database fails fast.
    """
    # Imported here rather than at module scope: models.py imports Base from
    # this module, so a top-level import would be circular. This registers
    # JobApplication in Base.metadata explicitly instead of relying on the
    # router import chain in main.py.
    from backend.app import models  # noqa: F401

    # Defense-in-depth: the lifespan already calls verify_schema instead in
    # public_demo, but create_all must never run there even if called.
    if load_settings().is_public_demo:
        raise SettingsError(
            "Refusing to run create_all: public_demo never creates tables."
        )

    target = get_engine() if bind is None else bind

    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=target)
            return
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay_seconds)


def verify_schema(
    bind=None,
    retries: int = 5,
    delay_seconds: float = 1.0,
) -> None:
    """public_demo startup check: every model table must already exist.

    Read-only: it inspects the catalog and never creates, alters, or drops
    anything. A missing table raises SchemaError (not retried), so startup
    fails closed. The schema must be created with owner credentials outside
    the public API process. Retries cover connection errors only, as in
    init_db.
    """
    from backend.app import models  # noqa: F401

    target = get_engine() if bind is None else bind

    for attempt in range(1, retries + 1):
        try:
            inspector = inspect(target)
            missing = [
                name
                for name in sorted(Base.metadata.tables)
                if not inspector.has_table(name)
            ]
            break
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay_seconds)

    if missing:
        raise SchemaError(
            f"Refusing to start: public_demo database is missing required "
            f"tables: {', '.join(missing)}. public_demo never creates tables."
        )
