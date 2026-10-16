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
public_demo startup never runs create_all; it only verifies the tables exist,
then verifies through the demo connection itself that the connected role is
strictly SELECT-only (verify_demo_role_privileges).

WARNING: read-only transactions are defense-in-depth, not a privilege
boundary -- a client can SET them off. The security boundary is the demo
role's actual privileges. The startup check refuses a role with too many
privileges, but the dedicated SELECT-only demo role is NOT provisioned yet,
so public_demo is still NOT SAFE TO DEPLOY.
Error messages name variables but never include their values.
"""

import os
import threading
import time
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, inspect, text
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

# public_demo connection pool (per process). Provisional; see
# create_read_only_engine.
PUBLIC_DEMO_POOL_SIZE = 2
PUBLIC_DEMO_MAX_OVERFLOW = 1
PUBLIC_DEMO_POOL_TIMEOUT_SECONDS = 10
PUBLIC_DEMO_POOL_RECYCLE_SECONDS = 1800

# --- public_demo privilege verification (verify_demo_role_privileges) ------
#
# Every query is a read-only catalog lookup that runs as the connected demo
# role. Privilege functions are applied only where they are valid for every
# row (has_table_privilege and has_schema_privilege accept any relation or
# schema). has_sequence_privilege raises an error for a non-sequence, and SQL
# does not guarantee WHERE evaluation order, so sequences are listed first
# and checked one statement at a time.

DEMO_ROLE_QUERY = (
    "SELECT session_user = current_user AS same_role, rolsuper, rolcreatedb, "
    "rolcreaterole, rolreplication, rolbypassrls "
    "FROM pg_roles WHERE rolname = current_user"
)
DEMO_MEMBERSHIPS_QUERY = (
    "SELECT roleid::regrole::text AS name FROM pg_auth_members "
    "WHERE member = current_user::regrole ORDER BY 1"
)
DEMO_OWNED_QUERY = (
    "SELECT 'database ' || CASE WHEN datname = current_database() "
    "THEN '(current)' ELSE datname END AS name FROM pg_database "
    "WHERE datdba = current_user::regrole "
    "UNION ALL SELECT 'schema ' || nspname FROM pg_namespace "
    "WHERE nspowner = current_user::regrole "
    "UNION ALL SELECT 'relation ' || oid::regclass::text FROM pg_class "
    "WHERE relowner = current_user::regrole "
    "ORDER BY 1"
)
# Catch-all across every database and object type (pg_shdepend is shared).
DEMO_OWNERSHIP_COUNT_QUERY = (
    "SELECT count(*) AS owned FROM pg_shdepend "
    "WHERE refclassid = 'pg_authid'::regclass "
    "AND refobjid = current_user::regrole AND deptype = 'o'"
)
DEMO_DATABASE_QUERY = (
    "SELECT has_database_privilege(current_database(), 'CREATE') AS can_create, "
    "has_database_privilege(current_database(), 'TEMPORARY') AS can_temp"
)
DEMO_SCHEMA_USAGE_QUERY = (
    "SELECT has_schema_privilege(CAST(:schema AS text), 'USAGE') AS can_use"
)
DEMO_SCHEMA_CREATE_QUERY = (
    "SELECT nspname::text AS name FROM pg_namespace "
    "WHERE has_schema_privilege(oid, 'CREATE') IS NOT FALSE ORDER BY 1"
)
# One row per required table; NULL (table missing) fails closed.
DEMO_TABLE_QUERY = (
    "SELECT has_table_privilege(t.oid, 'SELECT') AS can_select, "
    "has_table_privilege(t.oid, 'SELECT WITH GRANT OPTION') AS select_grant, "
    "has_table_privilege(t.oid, 'INSERT') AS can_insert, "
    "has_table_privilege(t.oid, 'UPDATE') AS can_update, "
    "has_table_privilege(t.oid, 'DELETE') AS can_delete, "
    "has_table_privilege(t.oid, 'TRUNCATE') AS can_truncate, "
    "has_table_privilege(t.oid, 'REFERENCES') AS can_references, "
    "has_table_privilege(t.oid, 'TRIGGER') AS can_trigger, "
    "has_any_column_privilege(t.oid, 'SELECT WITH GRANT OPTION') "
    "AS column_select_grant, "
    "has_any_column_privilege(t.oid, 'INSERT') AS column_insert, "
    "has_any_column_privilege(t.oid, 'UPDATE') AS column_update, "
    "has_any_column_privilege(t.oid, 'REFERENCES') AS column_references "
    "FROM (SELECT to_regclass(format('%I.%I', CAST(:schema AS text), "
    "CAST(:name AS text)))::oid AS oid) t"
)
# Every relation in this database, so a write grant on any table (not only
# the application's) is caught. One built-in exception: PostgreSQL grants
# UPDATE on the pg_catalog.pg_settings view to PUBLIC by default. Updating
# it is equivalent to SET for the current session (which every role can do
# anyway) and writes no data, so only UPDATE is exempted, and only there.
DEMO_WRITABLE_RELATIONS_QUERY = (
    "SELECT oid::regclass::text AS name FROM pg_class "
    "WHERE has_table_privilege(oid, CASE "
    "WHEN oid = 'pg_catalog.pg_settings'::regclass "
    "THEN 'SELECT WITH GRANT OPTION, INSERT, DELETE, TRUNCATE, REFERENCES, "
    "TRIGGER' "
    "ELSE 'SELECT WITH GRANT OPTION, INSERT, UPDATE, DELETE, TRUNCATE, "
    "REFERENCES, TRIGGER' END) IS NOT FALSE "
    "ORDER BY 1"
)
# Column-level ACLs granted to the role or to PUBLIC: anything beyond plain
# SELECT (a write privilege or any grant option).
DEMO_COLUMN_GRANTS_QUERY = (
    "SELECT DISTINCT a.attrelid::regclass::text AS name "
    "FROM pg_attribute a "
    "WHERE a.attnum > 0 AND NOT a.attisdropped "
    "AND ("
    "has_column_privilege(a.attrelid, a.attnum, 'SELECT WITH GRANT OPTION') "
    "OR has_column_privilege(a.attrelid, a.attnum, 'INSERT') "
    "OR (a.attrelid <> 'pg_catalog.pg_settings'::regclass "
    "AND has_column_privilege(a.attrelid, a.attnum, 'UPDATE')) "
    "OR has_column_privilege(a.attrelid, a.attnum, 'REFERENCES')"
    ") ORDER BY 1"
)
DEMO_SEQUENCES_QUERY = (
    "SELECT oid, oid::regclass::text AS name FROM pg_class "
    "WHERE relkind = 'S' ORDER BY 2"
)
DEMO_SEQUENCE_QUERY = (
    "SELECT has_sequence_privilege(CAST(:oid AS oid), 'USAGE') AS can_usage, "
    "has_sequence_privilege(CAST(:oid AS oid), 'SELECT') AS can_select, "
    "has_sequence_privilege(CAST(:oid AS oid), 'UPDATE') AS can_update"
)

DEMO_FORBIDDEN_ROLE_ATTRIBUTES = {
    "rolsuper": "SUPERUSER",
    "rolcreatedb": "CREATEDB",
    "rolcreaterole": "CREATEROLE",
    "rolreplication": "REPLICATION",
    "rolbypassrls": "BYPASSRLS",
}
DEMO_FORBIDDEN_TABLE_PRIVILEGES = {
    "select_grant": "SELECT WITH GRANT OPTION",
    "can_insert": "INSERT",
    "can_update": "UPDATE",
    "can_delete": "DELETE",
    "can_truncate": "TRUNCATE",
    "can_references": "REFERENCES",
    "can_trigger": "TRIGGER",
    "column_select_grant": "column SELECT WITH GRANT OPTION",
    "column_insert": "column INSERT",
    "column_update": "column UPDATE",
    "column_references": "column REFERENCES",
}
DEMO_FORBIDDEN_SEQUENCE_PRIVILEGES = {
    "can_usage": "USAGE",
    "can_select": "SELECT",
    "can_update": "UPDATE",
}


class ReadOnlySessionError(RuntimeError):
    """Raised when a public_demo connection is not read-only as required."""


class SchemaError(RuntimeError):
    """Raised when public_demo finds the database schema incomplete."""


class DemoPrivilegeError(RuntimeError):
    """Raised when the public_demo database role is not strictly SELECT-only."""


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
    """Create a public_demo engine whose every connection is read-only.

    The pool is deliberately small (at most 3 connections per process) so
    the demo cannot exhaust the database's connection slots. These are
    provisional: the final limits depend on the Render plan's connection
    limit, the demo role's CONNECTION LIMIT, and the number of workers.
    """
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=PUBLIC_DEMO_POOL_SIZE,
        max_overflow=PUBLIC_DEMO_MAX_OVERFLOW,
        pool_timeout=PUBLIC_DEMO_POOL_TIMEOUT_SECONDS,
        pool_recycle=PUBLIC_DEMO_POOL_RECYCLE_SECONDS,
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


def _rows(connection, query: str, **params) -> list:
    return connection.execute(text(query), params).mappings().all()


DEMO_MAX_LISTED_NAMES = 10


def _names(names: list[str]) -> str:
    """Join names for an error message, truncating long lists."""
    shown = ", ".join(names[:DEMO_MAX_LISTED_NAMES])
    hidden = len(names) - DEMO_MAX_LISTED_NAMES
    return f"{shown} (+{hidden} more)" if hidden > 0 else shown


def _granted(value) -> bool:
    """Fail closed: anything other than an explicit False counts as granted."""
    return value is not False


def demo_privilege_problems(connection) -> list[str]:
    """Return every reason the connected role is not strictly SELECT-only.

    Read-only: catalog queries and privilege functions only. It never
    writes, runs DDL, switches roles, or grants anything. Messages name
    privileges, tables, and other roles, never the connected role, host,
    password, or the current database's name (shown as "(current)").
    """
    from backend.app import models  # noqa: F401

    problems: list[str] = []

    role = _rows(connection, DEMO_ROLE_QUERY)
    if len(role) != 1:
        problems.append("the connected role's attributes could not be read")
    else:
        attributes = role[0]
        if attributes["same_role"] is not True:
            problems.append(
                "session_user differs from current_user (SET ROLE in effect)"
            )
        for column, label in DEMO_FORBIDDEN_ROLE_ATTRIBUTES.items():
            if _granted(attributes[column]):
                problems.append(f"role has {label}")

    memberships = [row["name"] for row in _rows(connection, DEMO_MEMBERSHIPS_QUERY)]
    if memberships:
        problems.append(f"role is a member of: {_names(memberships)}")

    owned = [row["name"] for row in _rows(connection, DEMO_OWNED_QUERY)]
    if owned:
        problems.append(f"role owns: {_names(owned)}")
    owned_count = _rows(connection, DEMO_OWNERSHIP_COUNT_QUERY)[0]["owned"]
    if owned_count != 0:
        problems.append(f"role owns {owned_count} object(s) in the cluster")

    database_privileges = _rows(connection, DEMO_DATABASE_QUERY)[0]
    if _granted(database_privileges["can_create"]):
        problems.append("CREATE on the database")
    if _granted(database_privileges["can_temp"]):
        problems.append("TEMPORARY on the database")

    creatable = [row["name"] for row in _rows(connection, DEMO_SCHEMA_CREATE_QUERY)]
    if creatable:
        problems.append(f"CREATE on schema: {_names(creatable)}")

    tables = sorted(
        Base.metadata.tables.values(),
        key=lambda table: (table.schema or "public", table.name),
    )
    for schema in sorted({table.schema or "public" for table in tables}):
        usage = _rows(connection, DEMO_SCHEMA_USAGE_QUERY, schema=schema)[0]
        if usage["can_use"] is not True:
            problems.append(f"no USAGE on schema {schema}")

    for table in tables:
        schema = table.schema or "public"
        qualified = f"{schema}.{table.name}"
        privileges = _rows(
            connection, DEMO_TABLE_QUERY, schema=schema, name=table.name
        )[0]
        if privileges["can_select"] is not True:
            problems.append(f"no SELECT on {qualified}")
        denied = [
            label
            for column, label in DEMO_FORBIDDEN_TABLE_PRIVILEGES.items()
            if _granted(privileges[column])
        ]
        if denied:
            problems.append(f"{', '.join(denied)} on {qualified}")

    writable = [row["name"] for row in _rows(connection, DEMO_WRITABLE_RELATIONS_QUERY)]
    if writable:
        problems.append(
            f"write privilege or grant option on: {_names(writable)}"
        )

    column_grants = [row["name"] for row in _rows(connection, DEMO_COLUMN_GRANTS_QUERY)]
    if column_grants:
        problems.append(
            f"column-level write privilege or grant option on: "
            f"{_names(column_grants)}"
        )

    # Listed first, then checked one statement per sequence (see the
    # comment above DEMO_ROLE_QUERY).
    for sequence in _rows(connection, DEMO_SEQUENCES_QUERY):
        privileges = _rows(connection, DEMO_SEQUENCE_QUERY, oid=sequence["oid"])[0]
        granted = [
            label
            for column, label in DEMO_FORBIDDEN_SEQUENCE_PRIVILEGES.items()
            if _granted(privileges[column])
        ]
        if granted:
            problems.append(
                f"{', '.join(granted)} on sequence {sequence['name']}"
            )

    return problems


def verify_demo_role_privileges(
    bind=None,
    retries: int = 5,
    delay_seconds: float = 1.0,
) -> None:
    """public_demo startup check: the demo role must be strictly SELECT-only.

    Runs through the configured demo engine itself (never an owner or
    superuser connection), so it checks the role the API actually uses.
    The role's privileges are the security boundary; the read-only session
    settings are only defense-in-depth. Any problem raises
    DemoPrivilegeError, so startup fails closed. Retries cover connection
    errors only, as in verify_schema. Checked once at startup: grants
    changed later are not detected until the next restart.
    """
    target = get_engine() if bind is None else bind

    for attempt in range(1, retries + 1):
        try:
            with target.connect() as connection:
                problems = demo_privilege_problems(connection)
            break
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay_seconds)

    if problems:
        raise DemoPrivilegeError(
            "Refusing to start: the public_demo database role is not "
            f"strictly SELECT-only: {'; '.join(problems)}."
        )
