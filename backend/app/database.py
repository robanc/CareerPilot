
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
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
