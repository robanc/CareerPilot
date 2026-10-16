"""Database engine and session configuration.

The engine is created lazily, on first use, from the operating mode in
settings.py -- never at module import -- so importing this module (or the
app) builds no engine and reads no database credentials.

- ``local``: connects with the POSTGRES_* variables (locally from ``.env``),
  exactly as before.
- ``public_demo``: connects only with Settings.demo_database_url
  (CAREERPILOT_DEMO_DATABASE_URL). POSTGRES_* are ignored even when set, and
  there is no fallback: a missing or invalid demo URL raises SettingsError.

WARNING: this only selects which credentials are used. The demo role's
PostgreSQL privileges and read-only transactions are NOT enforced yet, so
public_demo is still NOT SAFE TO DEPLOY. Error messages name variables but
never include their values.
"""

import os
import threading
import time
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
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


def create_engine_for(settings: Settings) -> Engine:
    """Create (but do not connect) the engine for the given mode."""
    return create_engine(database_url_for(settings), pool_pre_ping=True)


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

    target = get_engine() if bind is None else bind

    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=target)
            return
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay_seconds)
