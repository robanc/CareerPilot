"""The live test-database guard in db_safety.py.

Connections, engines, and metadata are fakes; only the last test uses the
real careerpilot_test engine, and it only runs SELECT current_database().
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.tests.db_safety import (
    TEST_DATABASE_NAME,
    UnsafeTestDatabaseError,
    require_test_database,
    reset_test_schema,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeConnection:
    def __init__(self, configured, live=None, error=None):
        self.engine = SimpleNamespace(url=SimpleNamespace(database=configured))
        self.live = live
        self.error = error
        self.executed = []

    def execute(self, statement):
        self.executed.append(str(statement))
        if self.error is not None:
            raise self.error
        return FakeResult(self.live)


class FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def begin(self):
        yield self.connection


class RecordingMetadata:
    def __init__(self):
        self.calls = []

    def drop_all(self, bind):
        self.calls.append(("drop_all", bind))

    def create_all(self, bind):
        self.calls.append(("create_all", bind))


def test_accepts_configured_and_live_test_database():
    connection = FakeConnection(TEST_DATABASE_NAME, live=TEST_DATABASE_NAME)

    require_test_database(connection)

    assert connection.executed == ["SELECT current_database()"]


def test_refuses_wrong_configured_name_without_querying():
    connection = FakeConnection("careerpilot", live=TEST_DATABASE_NAME)

    with pytest.raises(UnsafeTestDatabaseError, match="configured"):
        require_test_database(connection)

    assert connection.executed == []


@pytest.mark.parametrize(
    "live",
    [
        "careerpilot",
        "CAREERPILOT_TEST",
        "careerpilot_test ",
        "careerpilot_test_old",
        "",
        None,
        b"careerpilot_test",
    ],
)
def test_refuses_when_live_database_differs(live):
    """The URL can say careerpilot_test while the server says otherwise,
    e.g. through a proxy or a service file; only an exact match passes."""
    connection = FakeConnection(TEST_DATABASE_NAME, live=live)

    with pytest.raises(UnsafeTestDatabaseError, match="live"):
        require_test_database(connection)


def test_refuses_lookalike_str_that_claims_equality():
    class AlwaysEqual:
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

    connection = FakeConnection(TEST_DATABASE_NAME, live=AlwaysEqual())

    with pytest.raises(UnsafeTestDatabaseError):
        require_test_database(connection)


def test_check_errors_propagate():
    connection = FakeConnection(
        TEST_DATABASE_NAME, error=RuntimeError("connection lost")
    )

    with pytest.raises(RuntimeError, match="connection lost"):
        require_test_database(connection)


@pytest.mark.parametrize(
    "connection",
    [
        FakeConnection("careerpilot", live="careerpilot"),
        FakeConnection(TEST_DATABASE_NAME, live="careerpilot"),
        FakeConnection(TEST_DATABASE_NAME, error=RuntimeError("check failed")),
    ],
    ids=["configured-dev", "live-dev", "check-error"],
)
def test_reset_never_cleans_up_when_check_fails(connection):
    metadata = RecordingMetadata()

    with pytest.raises((UnsafeTestDatabaseError, RuntimeError)):
        reset_test_schema(FakeEngine(connection), metadata)

    assert metadata.calls == []


def test_reset_cleans_up_on_the_checked_connection():
    connection = FakeConnection(TEST_DATABASE_NAME, live=TEST_DATABASE_NAME)
    metadata = RecordingMetadata()

    reset_test_schema(FakeEngine(connection), metadata)

    assert connection.executed == ["SELECT current_database()"]
    assert metadata.calls == [("drop_all", connection), ("create_all", connection)]


def test_real_test_engine_is_live_on_test_database(test_db_engine):
    with test_db_engine.connect() as connection:
        require_test_database(connection)
