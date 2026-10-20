
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base, get_db, local_database_url, reset_engine
from backend.app.limits import rate_limiter
from backend.app.main import app
import backend.app.models  # Register database models
from backend.tests.db_safety import reset_test_schema


# Built from the local POSTGRES_* settings, with the database name forced to
# careerpilot_test. Tests never use the app's lazily created engine.
TEST_DATABASE_URL = local_database_url().set(
    database="careerpilot_test"
)

# Only the isolated test container (docker-compose.test.yml publishes it on
# 127.0.0.1:5433; development uses 5432). Checked before any engine exists,
# so a wrong POSTGRES_HOST/POSTGRES_PORT stops the run at collection time.
# An explicit raise, not an assert, so "python -O" cannot remove it.
TEST_DATABASE_ENDPOINT = ("127.0.0.1", 5433)
if (TEST_DATABASE_URL.host, TEST_DATABASE_URL.port) != TEST_DATABASE_ENDPOINT:
    raise RuntimeError(
        "Refusing to run backend tests: POSTGRES_HOST/POSTGRES_PORT must "
        "point at the isolated test database on 127.0.0.1:5433."
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
def reset_rate_limits():
    """Rate limit counters are process-wide; start every test unthrottled."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture(autouse=True)
def use_test_database():
    # Safety check: never run cleanup against development database.
    assert TEST_DATABASE_URL.database == "careerpilot_test"

    # Reset test tables before each test, only after confirming the live
    # current_database() on the same connection. See db_safety.py.
    reset_test_schema(test_engine, Base.metadata)

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
        # Drop any engine a test built, so none leaks into the next test.
        reset_engine()

