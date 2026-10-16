
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.engine import URL


# Project root: C:\Users\roban\CareerPilot
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load local database settings without overriding existing environment variables.
load_dotenv(PROJECT_ROOT / ".env")


DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    database=os.environ["POSTGRES_DB"],
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
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

    target = engine if bind is None else bind

    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=target)
            return
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay_seconds)
