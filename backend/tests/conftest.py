
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base, DATABASE_URL, get_db
from backend.app.main import app
import backend.app.models  # Register database models


TEST_DATABASE_URL = DATABASE_URL.set(
    database="careerpilot_test"
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)



@pytest.fixture
def test_db_engine():
    """Expose the test engine so tests can target it explicitly."""
    return test_engine


@pytest.fixture(autouse=True)
def use_test_database():
    # Safety check: never run cleanup against development database.
    assert TEST_DATABASE_URL.database == "careerpilot_test"

    # Reset test tables before each test.
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)

