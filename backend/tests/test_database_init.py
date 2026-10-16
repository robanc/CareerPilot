from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend.app.database import Base, init_db
from backend.app.main import app


client = TestClient(app)


TABLE_NAME = "job_applications"


def assert_targets_test_database(engine):
    """Guard: refuse to touch anything but the dedicated test database."""
    assert engine.url.database == "careerpilot_test", (
        f"Refusing to run: engine targets {engine.url.database!r}, "
        "not 'careerpilot_test'"
    )


def test_init_db_creates_missing_table(test_db_engine):
    """A fresh database (no tables) gets the schema created.

    This is the fresh-docker-compose scenario the fix exists for.
    """
    assert_targets_test_database(test_db_engine)

    # Start from an empty schema. Confined to careerpilot_test by the guard
    # above; mirrors what the autouse fixture already does per test.
    Base.metadata.drop_all(bind=test_db_engine)

    assert not inspect(test_db_engine).has_table(TABLE_NAME)

    init_db(bind=test_db_engine)

    assert inspect(test_db_engine).has_table(TABLE_NAME)


def test_init_db_preserves_existing_rows(test_db_engine):
    """Running init_db against a populated database must not lose data."""
    assert_targets_test_database(test_db_engine)

    payload = {
        "company_name": "Persistence Check Ltd",
        "job_title": "Platform Engineer",
        "application_date": "2026-10-16",
        "status": "Applied",
    }

    create_response = client.post("/applications", json=payload)

    assert create_response.status_code == 201

    application_id = create_response.json()["id"]

    count_before = len(client.get("/applications").json())

    # Simulate repeated container restarts against a populated database.
    init_db(bind=test_db_engine)
    init_db(bind=test_db_engine)

    # The row survives untouched.
    get_response = client.get(f"/applications/{application_id}")

    assert get_response.status_code == 200
    assert get_response.json()["company_name"] == "Persistence Check Ltd"
    assert get_response.json()["status"] == "Applied"

    # And nothing else was dropped or truncated.
    assert len(client.get("/applications").json()) == count_before


def test_init_db_is_idempotent(test_db_engine):
    """Repeated calls succeed without error, as on every container restart."""
    assert_targets_test_database(test_db_engine)

    init_db(bind=test_db_engine)
    init_db(bind=test_db_engine)
    init_db(bind=test_db_engine)

    assert inspect(test_db_engine).has_table(TABLE_NAME)
