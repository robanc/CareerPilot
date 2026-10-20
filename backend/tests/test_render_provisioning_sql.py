"""Render provisioning SQL drafts (deploy/render/*.sql.review).

Static checks on all three drafts, plus a check that the schema DDL in
01_render_schema creates exactly what the SQLAlchemy models create. That
check runs the DDL in a throwaway schema of the isolated test database,
inside a transaction that is always rolled back; the drafts themselves are
never executed (their identity checks would refuse the test cluster).
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import inspect, text


RENDER_DIR = Path(__file__).resolve().parents[2] / "deploy" / "render"
SCHEMA_SQL = RENDER_DIR / "01_render_schema.sql.review"
ROLE_SQL = RENDER_DIR / "02_render_demo_role.sql.review"
VERIFY_SQL = RENDER_DIR / "03_render_demo_role_verify.sql.review"
DRAFTS = [SCHEMA_SQL, ROLE_SQL, VERIFY_SQL]
CHECK_SCHEMA = "render_ddl_check"


def code_only(sql: str) -> str:
    """SQL without -- comments, for keyword checks."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def schema_ddl() -> list[str]:
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    block = sql.split("-- BEGIN SCHEMA DDL", 1)[1].split("-- END SCHEMA DDL", 1)[0]
    return [statement.strip() for statement in block.split(";") if statement.strip()]


@pytest.mark.parametrize("path", DRAFTS, ids=lambda p: p.name)
def test_drafts_are_review_only_and_stop_on_error(path):
    sql = path.read_text(encoding="utf-8")
    assert "REVIEW DRAFT ONLY" in sql
    assert "\\set ON_ERROR_STOP on" in sql
    assert sql.isascii()


@pytest.mark.parametrize("path", DRAFTS, ids=lambda p: p.name)
def test_drafts_contain_no_destructive_or_credential_statements(path):
    code = code_only(path.read_text(encoding="utf-8")).upper()
    for pattern in [
        r"\bDROP\b", r"\bTRUNCATE\s+(TABLE\s+)?\w", r"\bDELETE\s+FROM\b",
        r"\bALTER\s+(ROLE|USER|SYSTEM|DATABASE)\b", r"\bPASSWORD\s+'",
        r"\bSET\s+ROLE\b", r"\bCOPY\b",
    ]:
        assert not re.search(pattern, code), pattern


def test_schema_and_role_scripts_are_single_transactions():
    for path in (SCHEMA_SQL, ROLE_SQL):
        code = code_only(path.read_text(encoding="utf-8"))
        assert re.findall(r"^BEGIN;$", code, re.M) == ["BEGIN;"]
        assert re.findall(r"^COMMIT;$", code, re.M) == ["COMMIT;"]
    verify = code_only(VERIFY_SQL.read_text(encoding="utf-8"))
    assert not re.search(r"^(BEGIN|COMMIT);", verify, re.M)


def test_role_script_includes_the_verifier_before_commit():
    code = code_only(ROLE_SQL.read_text(encoding="utf-8"))
    include = code.index("\\ir 03_render_demo_role_verify.sql")
    assert include < code.index("COMMIT;")
    assert (RENDER_DIR / "03_render_demo_role_verify.sql.review").exists()


def test_role_is_created_without_a_password_or_special_attributes():
    code = code_only(ROLE_SQL.read_text(encoding="utf-8"))
    create = code[code.index("CREATE ROLE"):code.index(";", code.index("CREATE ROLE"))]
    for attribute in [
        "LOGIN", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE", "NOINHERIT",
        "NOREPLICATION", "NOBYPASSRLS", "PASSWORD NULL",
    ]:
        assert attribute in create


def test_render_schema_ddl_matches_the_models(test_db_engine):
    # conftest has just created the model tables in public via create_all.
    with test_db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f"CREATE SCHEMA {CHECK_SCHEMA}"))
            connection.execute(text(f"SET LOCAL search_path TO {CHECK_SCHEMA}"))
            for statement in schema_ddl():
                connection.execute(text(statement))

            inspector = inspect(connection)
            assert describe(inspector, CHECK_SCHEMA) == describe(inspector, "public")
        finally:
            transaction.rollback()


def describe(inspector, schema):
    tables = sorted(inspector.get_table_names(schema=schema))
    result = {}
    for table in tables:
        columns = [
            (
                column["name"],
                str(column["type"]),
                getattr(column["type"], "timezone", None),
                column["nullable"],
                column["default"] is not None,
            )
            for column in inspector.get_columns(table, schema=schema)
        ]
        primary_key = inspector.get_pk_constraint(table, schema=schema)[
            "constrained_columns"
        ]
        indexes = sorted(
            (index["name"], tuple(index["column_names"]), index["unique"])
            for index in inspector.get_indexes(table, schema=schema)
        )
        result[table] = (columns, primary_key, indexes)
    return result
