"""Real privilege tests for the careerpilot_test_reader role.

careerpilot_test only. The role is provisioned out of band by
backend/tests/sql/01_test_reader_role.sql and 02_test_reader_grants.sql;
these tests never create, alter, or grant anything. If the role is missing
or its privileges are wrong, the tests FAIL -- they never skip.

How the role is entered: a dedicated NullPool engine opens a connection with
the normal test (superuser) credentials, starts a transaction, runs the live
require_test_database() guard, and only then runs SET LOCAL ROLE. Every probe
statement runs after that, as the reader. The transaction is always rolled
back, and NullPool closes the connection, so the role cannot leak.

NOT A SECURITY BOUNDARY: SET ROLE from a superuser session tests the
reader's grants, not login containment. session_user stays the superuser,
which can always RESET ROLE. These tests prove what the role's privileges
allow; they do not prove that a client logged in some other way is confined.
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from backend.tests.db_safety import TEST_DATABASE_NAME, require_test_database


READER_ROLE = "careerpilot_test_reader"
INSUFFICIENT_PRIVILEGE = "42501"

SEED_ROW = (
    "INSERT INTO job_applications (company_name, job_title, "
    "application_date, status, created_at, updated_at) VALUES "
    "('Synthetic Co', 'Synthetic Role', '2026-10-16', 'Saved', now(), now())"
)


@pytest.fixture
def reader_engine(test_db_engine):
    """A separate engine with no pooling, so no role-switched connection is
    ever reused."""
    engine = create_engine(test_db_engine.url, poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.dispose()


@contextmanager
def reader_transaction(engine):
    """Yield a connection whose current transaction runs as the reader.

    The guard runs first, on the same connection and in the same transaction.
    The transaction is always rolled back, including when a probe that
    should have failed succeeds.
    """
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            require_test_database(connection)

            exists = connection.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
                {"role": READER_ROLE},
            ).scalar_one_or_none()
            if exists is None:
                pytest.fail(
                    f"{READER_ROLE} does not exist in this cluster. Provision "
                    "it with backend/tests/sql/01_test_reader_role.sql and "
                    "02_test_reader_grants.sql."
                )

            connection.execute(text(f"SET LOCAL ROLE {READER_ROLE}"))
            current = connection.execute(text("SELECT current_user")).scalar_one()
            if current != READER_ROLE:
                pytest.fail(f"SET LOCAL ROLE left current_user as {current!r}.")

            yield connection
        finally:
            if transaction.is_active:
                transaction.rollback()


def seed_one_row(test_db_engine):
    """Insert one synthetic row as the owner, in its own guarded transaction.

    The autouse fixture drops and recreates the tables before every test.
    """
    with test_db_engine.begin() as connection:
        require_test_database(connection)
        connection.execute(text(SEED_ROW))


def assert_insufficient_privilege(connection, statement):
    with pytest.raises(DBAPIError) as excinfo:
        connection.execute(text(statement))
    sqlstate = getattr(excinfo.value.orig, "sqlstate", None)
    assert sqlstate == INSUFFICIENT_PRIVILEGE, (
        f"Expected SQLSTATE {INSUFFICIENT_PRIVILEGE}, got {sqlstate!r}: "
        f"{excinfo.value.orig}"
    )


# --- identity and attributes ------------------------------------------------


def test_reader_session_identity(reader_engine):
    with reader_transaction(reader_engine) as connection:
        row = connection.execute(
            text("SELECT current_database(), current_user, session_user")
        ).one()

    assert row[0] == TEST_DATABASE_NAME
    assert row[1] == READER_ROLE
    # The probe session is still owned by the superuser; see module docstring.
    assert row[2] != READER_ROLE


def test_reader_role_attributes_are_restrictive(reader_engine):
    with reader_transaction(reader_engine) as connection:
        role = connection.execute(
            text(
                "SELECT rolsuper, rolcanlogin, rolinherit, rolcreatedb, "
                "rolcreaterole, rolreplication, rolbypassrls, rolconnlimit "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).mappings().one()
        memberships = connection.execute(
            text(
                "SELECT count(*) FROM pg_auth_members "
                "WHERE member = current_user::regrole "
                "OR roleid = current_user::regrole"
            )
        ).scalar_one()
        data_roles = connection.execute(
            text(
                "SELECT pg_has_role(current_user, 'pg_read_all_data', 'MEMBER'), "
                "pg_has_role(current_user, 'pg_write_all_data', 'MEMBER')"
            )
        ).one()

    assert dict(role) == {
        "rolsuper": False,
        "rolcanlogin": False,
        "rolinherit": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolreplication": False,
        "rolbypassrls": False,
        "rolconnlimit": 0,
    }
    assert memberships == 0
    assert tuple(data_roles) == (False, False)


# --- allowed: SELECT --------------------------------------------------------


def test_reader_can_select(reader_engine, test_db_engine):
    seed_one_row(test_db_engine)

    with reader_transaction(reader_engine) as connection:
        rows = connection.execute(
            text("SELECT company_name FROM job_applications")
        ).scalars().all()

    assert rows == ["Synthetic Co"]


# --- rejected: each in its own transaction ----------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        SEED_ROW,
        "UPDATE job_applications SET notes = 'changed'",
        "DELETE FROM job_applications",
        "TRUNCATE job_applications",
        "CREATE TABLE reader_probe (id int)",
        "CREATE TEMP TABLE reader_probe (id int)",
        "SELECT nextval(pg_get_serial_sequence('job_applications', 'id'))",
    ],
    ids=["insert", "update", "delete", "truncate", "create-table",
         "create-temp-table", "nextval"],
)
def test_reader_write_is_rejected(reader_engine, test_db_engine, statement):
    seed_one_row(test_db_engine)

    with reader_transaction(reader_engine) as connection:
        assert_insufficient_privilege(connection, statement)

    # Nothing changed, checked as the owner after the rollback.
    with test_db_engine.connect() as connection:
        require_test_database(connection)
        assert connection.execute(
            text("SELECT count(*) FROM job_applications")
        ).scalar_one() == 1
        assert connection.execute(
            text("SELECT to_regclass('public.reader_probe')")
        ).scalar_one() is None
