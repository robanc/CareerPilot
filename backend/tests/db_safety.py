"""Live guard for destructive test cleanup (drop_all / create_all).

The URL-name guard in conftest.py checks only what the engine was configured
with. This also asks the server which database the connection is actually
on, and does so on the same connection -- and in the same transaction --
that then runs the cleanup, so the check cannot pass on one database while
the cleanup runs on another.

Fail-closed rules:
- Explicit raises, not asserts, so ``python -O`` cannot strip the check.
- Exact, case-sensitive match on a str; anything else is refused.
- Any error while checking propagates, so a failed check never permits
  cleanup. There is no override or skip switch.
"""

from sqlalchemy import text


TEST_DATABASE_NAME = "careerpilot_test"


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when destructive test cleanup targets the wrong database."""


def require_test_database(connection) -> None:
    """Raise unless the connection is configured for and live on the test DB."""
    configured = connection.engine.url.database
    if configured != TEST_DATABASE_NAME:
        raise UnsafeTestDatabaseError(
            f"Refusing test cleanup: engine is configured for "
            f"{configured!r}, not {TEST_DATABASE_NAME!r}."
        )

    live = connection.execute(text("SELECT current_database()")).scalar_one()
    if not isinstance(live, str) or live != TEST_DATABASE_NAME:
        raise UnsafeTestDatabaseError(
            f"Refusing test cleanup: connection is live on {live!r}, "
            f"not {TEST_DATABASE_NAME!r}."
        )


def reset_test_schema(engine, metadata) -> None:
    """Drop and recreate all tables, only after the live check passes.

    The check, drop_all, and create_all share one connection and one
    transaction (PostgreSQL DDL is transactional), so a failed check
    leaves the database untouched.
    """
    with engine.begin() as connection:
        require_test_database(connection)
        metadata.drop_all(bind=connection)
        metadata.create_all(bind=connection)
