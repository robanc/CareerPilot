"""Seed fictional job applications for the public demo.

Usage, from the repository root (a dry run unless --apply is given):

    CAREERPILOT_SEED_DATABASE_URL=<owner URL> \\
        python -m backend.scripts.seed_demo_data \\
            --expect-database careerpilot_demo \\
            --expect-host <host> --expect-user <user> \\
            [--apply --confirm <user>@<host>/careerpilot_demo]

Every record is invented: company names end in "(Demo)", job URLs use the
reserved example.com domain, and no record names a person. Each record's
notes end with a "[seed:<key>]" marker, which is how the script recognizes
its own rows.

Safety rules. Any failure stops the script before it writes anything:

- The target comes only from CAREERPILOT_SEED_DATABASE_URL. The script never
  reads .env or POSTGRES_* and never imports backend.app.database (which
  loads .env), so it cannot fall back to the development database.
- The target is named three times and must agree everywhere: the URL, the
  --expect-database/--expect-host/--expect-user arguments, and (for the
  database and user) the live session. --apply additionally requires
  --confirm <user>@<host>/<database>, typed out exactly.
- Only allowlisted database names are accepted (ALLOWED_DATABASES).
- A loopback host on port 5432 (the development stack) is refused.
- TLS is required: the URL may not weaken sslmode, and the live session
  must report an encrypted TCP connection.
- The live role must not be a superuser (the development and test
  containers connect as superusers), and the server must run PostgreSQL 16.
- The job_applications table must already exist (the script never creates
  or alters tables) and may contain only seed rows. A single row without a
  seed marker means real or development data, and the script refuses.
- Idempotent: rows are matched by marker, inserted when missing and updated
  when present (interview dates are relative to today, so re-running keeps
  upcoming interviews in the future). It never deletes anything.
- The plan is computed with reads only. A dry run executes in a READ ONLY
  transaction; --apply writes in one transaction.
- The database URL and credentials are never printed.
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.engine import URL, Connection, make_url

from backend.app.schemas import ApplicationCreate


SEED_URL_ENV_VAR = "CAREERPILOT_SEED_DATABASE_URL"
TABLE_NAME = "job_applications"
MARKER_PATTERN = re.compile(r"\[seed:([a-z0-9-]+)\]\s*$")
ALLOWED_DATABASES = frozenset({"careerpilot_demo"})
REQUIRED_SERVER_MAJOR_VERSION = 16
TLS_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})
LOOPBACK_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}
)
DEVELOPMENT_PORT = 5432


class SeedError(RuntimeError):
    """Raised when seeding is refused. Messages never contain credentials."""


@dataclass(frozen=True)
class SeedRecord:
    key: str
    company_name: str
    job_title: str
    status: str
    applied_days_ago: int
    job_description: str
    notes: str
    interview_in_days: int | None = None
    interview_hour_utc: int = 15
    interview_notes: str | None = None


SEED_RECORDS = (
    SeedRecord(
        key="northwind-backend",
        company_name="Northwind Robotics (Demo)",
        job_title="Backend Engineer",
        status="Applied",
        applied_days_ago=6,
        job_description=(
            "Build Python and FastAPI services backed by PostgreSQL. "
            "Experience with Docker and AWS is a plus."
        ),
        notes="Submitted through the careers page.",
    ),
    SeedRecord(
        key="blue-harbor-data",
        company_name="Blue Harbor Analytics (Demo)",
        job_title="Data Analyst",
        status="Interview",
        applied_days_ago=14,
        job_description=(
            "Data analysis with SQL and Python; dashboards for "
            "operations teams. Machine learning familiarity preferred."
        ),
        notes="Recruiter screen went well.",
        interview_in_days=3,
        interview_notes="Prepare a short walkthrough of a SQL analysis project.",
    ),
    SeedRecord(
        key="cedar-peak-frontend",
        company_name="Cedar Peak Software (Demo)",
        job_title="Frontend Developer",
        status="Interview",
        applied_days_ago=10,
        job_description=(
            "React and JavaScript single-page applications, with Git-based "
            "code review and CI/CD pipelines."
        ),
        notes="Take-home exercise submitted.",
        interview_in_days=8,
        interview_hour_utc=17,
        interview_notes="Review accessibility basics and React state patterns.",
    ),
    SeedRecord(
        key="silverline-devops",
        company_name="Silverline Health Tech (Demo)",
        job_title="DevOps Engineer",
        status="Saved",
        applied_days_ago=2,
        job_description=(
            "Kubernetes, Terraform, and Linux administration for a cloud "
            "computing platform on Azure."
        ),
        notes="Tailor the resume before applying.",
    ),
    SeedRecord(
        key="maple-grid-cloud",
        company_name="Maple Grid Energy (Demo)",
        job_title="Cloud Engineer",
        status="Offer",
        applied_days_ago=40,
        job_description=(
            "Design AWS infrastructure with Terraform and Docker; "
            "networking experience required."
        ),
        notes="Offer received; reviewing details.",
        interview_in_days=-12,
        interview_notes="Final round covered networking and incident response.",
    ),
    SeedRecord(
        key="orchid-python",
        company_name="Orchid Learning (Demo)",
        job_title="Junior Python Developer",
        status="Rejected",
        applied_days_ago=35,
        job_description="Python, Django, and SQL for an online learning product.",
        notes="Position filled internally.",
        interview_in_days=-20,
        interview_notes="Asked about Django ORM performance.",
    ),
    SeedRecord(
        key="quartz-sre",
        company_name="Quartz Logistics (Demo)",
        job_title="Site Reliability Engineer",
        status="Applied",
        applied_days_ago=4,
        job_description=(
            "Linux, Kubernetes, and Python automation; on-call rotation "
            "for a 5G-connected fleet platform."
        ),
        notes="Referred by a former colleague.",
    ),
    SeedRecord(
        key="lumen-fullstack",
        company_name="Lumen Civic Labs (Demo)",
        job_title="Full Stack Engineer",
        status="Interview",
        applied_days_ago=18,
        job_description=(
            "JavaScript, React, Python, and PostgreSQL for public-sector "
            "web services. Docker and Git required."
        ),
        notes="Second interview scheduled.",
        interview_in_days=15,
        interview_hour_utc=14,
        interview_notes="System design: a small case-tracking service.",
    ),
)


def marker(key: str) -> str:
    return f"[seed:{key}]"


def seed_key(notes: str | None) -> str | None:
    """The seed key in a row's notes, or None for a non-seed row."""
    if not notes:
        return None
    match = MARKER_PATTERN.search(notes)
    return match.group(1) if match else None


def build_row(record: SeedRecord, today: date) -> dict:
    """Column values for one record, validated against the API schema."""
    interview_at = None
    if record.interview_in_days is not None:
        interview_at = datetime.combine(
            today + timedelta(days=record.interview_in_days),
            time(hour=record.interview_hour_utc),
            tzinfo=timezone.utc,
        )

    candidate = ApplicationCreate(
        company_name=record.company_name,
        job_title=record.job_title,
        job_description=record.job_description,
        application_date=today - timedelta(days=record.applied_days_ago),
        status=record.status,
        job_url=f"https://example.com/careers/{record.key}",
        notes=f"Fictional demo record. {record.notes} {marker(record.key)}",
        interview_at=interview_at,
        interview_notes=record.interview_notes,
    )
    return candidate.model_dump(mode="json") | {
        "application_date": candidate.application_date,
        "interview_at": candidate.interview_at,
    }


@dataclass(frozen=True)
class SeedTarget:
    database: str
    host: str
    user: str

    @property
    def confirmation(self) -> str:
        return f"{self.user}@{self.host}/{self.database}"


def check_target(raw_url: str | None, target: SeedTarget) -> URL:
    """Validate the URL against the expected target before connecting.

    Fails closed and never echoes the URL or any credential.
    """
    if not raw_url or not raw_url.strip():
        raise SeedError(f"{SEED_URL_ENV_VAR} is not set.")
    try:
        url = make_url(raw_url.strip())
    except Exception:
        raise SeedError(f"{SEED_URL_ENV_VAR} is not a valid database URL.") from None

    if url.get_backend_name() != "postgresql":
        raise SeedError(f"{SEED_URL_ENV_VAR} must be a PostgreSQL URL.")
    if target.database not in ALLOWED_DATABASES:
        raise SeedError(
            "--expect-database is not an allowed seed target (allowed: "
            f"{', '.join(sorted(ALLOWED_DATABASES))})."
        )

    host = (url.host or "localhost").lower()
    port = url.port or DEVELOPMENT_PORT
    if host in LOOPBACK_HOSTS and port == DEVELOPMENT_PORT:
        raise SeedError(
            "Refusing a loopback host on port 5432: that is the development "
            "database."
        )
    if url.database != target.database:
        raise SeedError(
            "--expect-database does not match the database named in "
            f"{SEED_URL_ENV_VAR}."
        )
    if host != target.host.lower():
        raise SeedError(
            f"--expect-host does not match the host named in {SEED_URL_ENV_VAR}."
        )
    if url.username != target.user:
        raise SeedError(
            f"--expect-user does not match the user named in {SEED_URL_ENV_VAR}."
        )

    sslmode = url.query.get("sslmode")
    if sslmode is None:
        url = url.update_query_dict({"sslmode": "require"})
    elif sslmode not in TLS_SSLMODES:
        raise SeedError(
            f"{SEED_URL_ENV_VAR} must not weaken sslmode; use require, "
            "verify-ca, or verify-full."
        )

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


LIVE_IDENTITY_QUERY = text(
    "SELECT current_database() AS database, current_user AS user_name, "
    "session_user = current_user AS same_role, "
    "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS superuser, "
    "current_setting('server_version_num')::integer / 10000 AS major, "
    "inet_server_addr() IS NOT NULL AS tcp, "
    "COALESCE((SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()), false) "
    "AS tls"
)


def check_live_identity(connection: Connection, target: SeedTarget) -> None:
    """Confirm the live session is the expected target. Read-only."""
    live = connection.execute(LIVE_IDENTITY_QUERY).mappings().one()
    problems = []
    if live["database"] != target.database:
        problems.append("database name")
    if live["user_name"] != target.user or live["same_role"] is not True:
        problems.append("user")
    if live["superuser"] is not False:
        problems.append("role is a superuser")
    if live["major"] != REQUIRED_SERVER_MAJOR_VERSION:
        problems.append(f"server is not PostgreSQL {REQUIRED_SERVER_MAJOR_VERSION}")
    if live["tcp"] is not True or live["tls"] is not True:
        problems.append("connection is not TLS over TCP")
    if problems:
        raise SeedError(
            "The live session is not the expected seed target: "
            f"{'; '.join(problems)}."
        )


@dataclass
class SeedPlan:
    inserts: list[dict] = field(default_factory=list)
    updates: list[tuple[int, dict]] = field(default_factory=list)


def plan_seed(connection: Connection, expected_database: str, today: date) -> SeedPlan:
    """Read-only checks and the list of changes. Raises SeedError to refuse."""
    live = connection.execute(text("SELECT current_database()")).scalar_one()
    if live != expected_database:
        raise SeedError("The live database does not match --expect-database.")

    table = Table(TABLE_NAME, MetaData(), autoload_with=connection)
    rows = connection.execute(select(table.c.id, table.c.notes)).all()

    existing: dict[str, int] = {}
    for row_id, notes in rows:
        key = seed_key(notes)
        if key is None:
            raise SeedError(
                f"{TABLE_NAME} contains rows that are not demo seed rows; "
                "refusing to mix fictional data with other data."
            )
        existing.setdefault(key, row_id)

    plan = SeedPlan()
    for record in SEED_RECORDS:
        values = build_row(record, today)
        if record.key in existing:
            plan.updates.append((existing[record.key], values))
        else:
            plan.inserts.append(values)
    return plan


def apply_plan(connection: Connection, plan: SeedPlan, now: datetime) -> None:
    table = Table(TABLE_NAME, MetaData(), autoload_with=connection)
    for values in plan.inserts:
        connection.execute(
            table.insert().values(**values, created_at=now, updated_at=now)
        )
    for row_id, values in plan.updates:
        connection.execute(
            table.update()
            .where(table.c.id == row_id)
            .values(**values, updated_at=now)
        )


def seed(
    connection: Connection,
    expected_database: str,
    *,
    apply: bool,
    today: date | None = None,
    now: datetime | None = None,
) -> SeedPlan:
    """Plan, then apply when asked. The caller owns the transaction."""
    now = now or datetime.now(timezone.utc)
    plan = plan_seed(connection, expected_database, today or now.date())
    if apply:
        apply_plan(connection, plan, now)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--expect-database",
        required=True,
        help="Target database; must be allowlisted and match the URL and server.",
    )
    parser.add_argument(
        "--expect-host",
        required=True,
        help="Target host; must match the URL exactly.",
    )
    parser.add_argument(
        "--expect-user",
        required=True,
        help="Target user; must match the URL and the live session.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the changes. Without it, only report what would change.",
    )
    parser.add_argument(
        "--confirm",
        help="Required with --apply: <user>@<host>/<database>, typed exactly.",
    )
    args = parser.parse_args(argv)
    target = SeedTarget(
        database=args.expect_database,
        host=args.expect_host,
        user=args.expect_user,
    )

    try:
        if args.apply and args.confirm != target.confirmation:
            raise SeedError(
                "--apply requires --confirm <user>@<host>/<database> matching "
                "the expected target exactly."
            )
        url = check_target(os.environ.get(SEED_URL_ENV_VAR), target)
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                with connection.begin():
                    if not args.apply:
                        connection.execute(text("SET TRANSACTION READ ONLY"))
                    check_live_identity(connection, target)
                    plan = seed(connection, target.database, apply=args.apply)
        finally:
            engine.dispose()
    except SeedError as exc:
        print(f"seed refused: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        # Driver messages can include connection details; print the type only.
        print(f"seed failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    action = "applied" if args.apply else "dry run (nothing written)"
    print(
        f"{action}: {len(plan.inserts)} insert(s), {len(plan.updates)} update(s) "
        f"in database {target.database!r}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
