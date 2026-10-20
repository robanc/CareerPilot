"""Fictional demo seed script: data, target guards, and idempotency.

The database tests run only against the test engine from conftest.py
(careerpilot_test, reset before every test), never through the script's
own URL handling.
"""

from datetime import date, datetime, timezone
from urllib.parse import urlsplit

import pytest
from sqlalchemy import func, select

from backend.app.models import JobApplication
from backend.app.schemas import ApplicationCreate
from backend.scripts.seed_demo_data import (
    SEED_RECORDS,
    SeedError,
    SeedTarget,
    build_row,
    check_live_identity,
    check_target,
    main,
    seed,
    seed_key,
)


TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
TEST_DATABASE = "careerpilot_test"


# --- the data itself --------------------------------------------------------


def test_seed_keys_are_unique():
    keys = [record.key for record in SEED_RECORDS]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("record", SEED_RECORDS, ids=lambda r: r.key)
def test_seed_rows_are_valid_and_fictional(record):
    row = build_row(record, TODAY)

    # Valid for the API (build_row already validates; re-check explicitly).
    ApplicationCreate(**row)
    assert row["company_name"].endswith("(Demo)")
    assert urlsplit(row["job_url"]).hostname == "example.com"
    assert "@" not in " ".join(
        str(value) for value in row.values() if isinstance(value, str)
    )
    assert seed_key(row["notes"]) == record.key
    assert row["notes"].startswith("Fictional demo record.")


def test_seed_has_upcoming_and_past_interviews():
    interviews = [
        build_row(record, TODAY)["interview_at"]
        for record in SEED_RECORDS
        if record.interview_in_days is not None
    ]
    assert any(when > NOW for when in interviews)
    assert any(when < NOW for when in interviews)


def test_seed_key_requires_a_trailing_marker():
    assert seed_key(None) is None
    assert seed_key("My own note") is None
    assert seed_key("Fictional demo record. [seed:quartz-sre]") == "quartz-sre"
    assert seed_key("[seed:quartz-sre] then more text") is None


# --- target guards (no connection is made) ---------------------------------


DEMO = "careerpilot_demo"
REMOTE_HOST = "db.example.com"
OWNER = "careerpilot_owner"
TARGET = SeedTarget(database=DEMO, host=REMOTE_HOST, user=OWNER)
GOOD_URL = f"postgresql://{OWNER}:pw@{REMOTE_HOST}/{DEMO}"


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "   ",
        "not a url",
        "sqlite:///demo.db",
        f"mysql://{OWNER}:pw@{REMOTE_HOST}/{DEMO}",
    ],
)
def test_check_target_refuses_missing_or_non_postgres_urls(url):
    with pytest.raises(SeedError):
        check_target(url, TARGET)


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1:5432", "[::1]:5432", "host.docker.internal", ""],
)
def test_check_target_refuses_the_development_port_on_loopback(host):
    url = f"postgresql://{OWNER}:pw@{host}/{DEMO}"
    target = SeedTarget(database=DEMO, host=host or "localhost", user=OWNER)
    with pytest.raises(SeedError, match="development database"):
        check_target(url, target)


def test_check_target_refuses_databases_outside_the_allowlist():
    target = SeedTarget(database="careerpilot", host=REMOTE_HOST, user=OWNER)
    with pytest.raises(SeedError, match="not an allowed seed target"):
        check_target(f"postgresql://{OWNER}:pw@{REMOTE_HOST}/careerpilot", target)


@pytest.mark.parametrize(
    ("url", "argument"),
    [
        (f"postgresql://{OWNER}:pw@{REMOTE_HOST}/other_db", "--expect-database"),
        (f"postgresql://{OWNER}:pw@other.example.com/{DEMO}", "--expect-host"),
        (f"postgresql://someone_else:pw@{REMOTE_HOST}/{DEMO}", "--expect-user"),
    ],
)
def test_check_target_requires_every_identity_part_to_match(url, argument):
    with pytest.raises(SeedError, match=argument):
        check_target(url, TARGET)


@pytest.mark.parametrize("sslmode", ["disable", "allow", "prefer"])
def test_check_target_refuses_weakened_tls(sslmode):
    with pytest.raises(SeedError, match="sslmode"):
        check_target(f"{GOOD_URL}?sslmode={sslmode}", TARGET)


def test_check_target_never_echoes_credentials():
    url = f"postgresql://someone_else:s3cret-value@{REMOTE_HOST}/{DEMO}"
    with pytest.raises(SeedError) as excinfo:
        check_target(url, TARGET)
    assert "s3cret-value" not in str(excinfo.value)


def test_check_target_accepts_the_expected_remote_target_and_requires_tls():
    url = check_target(GOOD_URL, TARGET)
    assert url.drivername == "postgresql+psycopg"
    assert (url.database, url.host, url.username) == (DEMO, REMOTE_HOST, OWNER)
    assert url.query["sslmode"] == "require"

    stricter = check_target(f"{GOOD_URL}?sslmode=verify-full", TARGET)
    assert stricter.query["sslmode"] == "verify-full"


def test_main_refuses_without_the_seed_url(monkeypatch, capsys):
    monkeypatch.delenv("CAREERPILOT_SEED_DATABASE_URL", raising=False)
    args = ["--expect-database", DEMO, "--expect-host", REMOTE_HOST,
            "--expect-user", OWNER]

    assert main(args) == 3
    assert "is not set" in capsys.readouterr().err


@pytest.mark.parametrize(
    "confirm",
    [None, f"{OWNER}@{REMOTE_HOST}", f"{OWNER}@other.example.com/{DEMO}"],
)
def test_main_apply_requires_exact_confirmation(monkeypatch, capsys, confirm):
    # The URL would pass; the missing or wrong confirmation must stop it
    # before any connection is attempted.
    monkeypatch.setenv("CAREERPILOT_SEED_DATABASE_URL", GOOD_URL)
    args = ["--expect-database", DEMO, "--expect-host", REMOTE_HOST,
            "--expect-user", OWNER, "--apply"]
    if confirm is not None:
        args += ["--confirm", confirm]

    assert main(args) == 3
    assert "--confirm" in capsys.readouterr().err


def test_live_identity_refuses_the_test_database(test_db_engine):
    # The isolated test cluster connects as a superuser without TLS, so even
    # a matching name is refused; the same holds for the dev container.
    target = SeedTarget(
        database=TEST_DATABASE, host="127.0.0.1", user="careerpilot_test_admin"
    )
    with test_db_engine.connect() as connection:
        with pytest.raises(SeedError) as excinfo:
            check_live_identity(connection, target)

    message = str(excinfo.value)
    assert "superuser" in message
    assert "TLS" in message


# --- against the isolated test database ------------------------------------


def count_rows(connection):
    return connection.execute(
        select(func.count()).select_from(JobApplication.__table__)
    ).scalar_one()


def test_dry_run_writes_nothing(test_db_engine):
    with test_db_engine.begin() as connection:
        plan = seed(connection, TEST_DATABASE, apply=False, today=TODAY, now=NOW)
        assert len(plan.inserts) == len(SEED_RECORDS)
        assert count_rows(connection) == 0


def test_seed_is_idempotent(test_db_engine):
    with test_db_engine.begin() as connection:
        first = seed(connection, TEST_DATABASE, apply=True, today=TODAY, now=NOW)
    with test_db_engine.begin() as connection:
        second = seed(connection, TEST_DATABASE, apply=True, today=TODAY, now=NOW)
        assert count_rows(connection) == len(SEED_RECORDS)

    assert (len(first.inserts), len(first.updates)) == (len(SEED_RECORDS), 0)
    assert (len(second.inserts), len(second.updates)) == (0, len(SEED_RECORDS))


def test_reseeding_moves_interviews_relative_to_today(test_db_engine):
    later = date(2026, 12, 1)
    with test_db_engine.begin() as connection:
        seed(connection, TEST_DATABASE, apply=True, today=TODAY, now=NOW)
    with test_db_engine.begin() as connection:
        seed(connection, TEST_DATABASE, apply=True, today=later, now=NOW)
        dates = connection.execute(
            select(JobApplication.application_date)
        ).scalars().all()

    assert min(dates) > TODAY


def test_seed_refuses_tables_with_non_seed_rows(test_db_engine):
    with test_db_engine.begin() as connection:
        connection.execute(
            JobApplication.__table__.insert().values(
                company_name="Someone Else's Data",
                job_title="Engineer",
                application_date=TODAY,
                status="Applied",
                notes="Not a seed row",
                created_at=NOW,
                updated_at=NOW,
            )
        )

    with test_db_engine.begin() as connection:
        with pytest.raises(SeedError, match="not demo seed rows"):
            seed(connection, TEST_DATABASE, apply=True, today=TODAY, now=NOW)
        assert count_rows(connection) == 1


def test_seed_refuses_a_different_live_database(test_db_engine):
    with test_db_engine.begin() as connection:
        with pytest.raises(SeedError, match="live database"):
            seed(connection, "some_other_db", apply=True, today=TODAY, now=NOW)
        assert count_rows(connection) == 0


def test_seeded_rows_are_served_by_the_dashboard(test_db_engine):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with test_db_engine.begin() as connection:
        seed(connection, TEST_DATABASE, apply=True, today=TODAY, now=NOW)

    dashboard = TestClient(app).get("/dashboard").json()

    assert dashboard["total"] == len(SEED_RECORDS)
