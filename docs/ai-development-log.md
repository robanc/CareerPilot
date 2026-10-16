# CareerPilot — AI-Assisted Development Log

## Entry 001 — Database Initialization

**Date:** October 16, 2026  
**AI Coding Agent:** Claude Code 2.1.252  
**Development Method:** Human-supervised, agent-assisted implementation  
**Status:** Implemented and verified locally; pending Git commit

### Objective

Ensure that a fresh CareerPilot deployment automatically creates missing PostgreSQL tables without deleting existing application data.

### Agent Workflow

1. Claude Code performed a read-only review of the existing CareerPilot repository.
2. The agent identified missing database schema initialization during application startup.
3. The agent proposed an implementation plan using SQLAlchemy `Base.metadata.create_all()` and a FastAPI lifespan handler.
4. The developer reviewed and approved the plan before implementation.
5. Claude Code implemented the changes and added automated regression tests.
6. The developer independently rebuilt the Docker backend and verified the dashboard API.

### Files Changed

- `backend/app/database.py` — Added database initialization with bounded retries.
- `backend/app/main.py` — Added FastAPI lifespan initialization.
- `backend/tests/conftest.py` — Added a fixture exposing the test database engine.
- `backend/tests/test_database_init.py` — Added three initialization and data-preservation tests.

### Verification Results

- Backend automated tests: **17 passed, 0 failed**
- Existing tests preserved: **14 passed**
- New database initialization tests: **3 passed**
- Docker backend rebuild: **Successful**
- PostgreSQL health: **Healthy**
- Dashboard API: **Successful**
- Existing application records after restart: **2**

### Human Oversight

The developer approved the implementation plan, required explicit database safety checks, and independently verified the updated Docker backend.

Claude Code did not commit or push changes without approval.

### Limitations and Follow-Up

SQLAlchemy `create_all()` creates missing tables but does not migrate existing database schemas. A migration tool such as Alembic should be considered before future schema changes.

A fresh deployment using a completely empty PostgreSQL volume has not yet been tested end-to-end.

### Outcome

CareerPilot now initializes missing database tables during application startup, with automated tests covering initial creation, idempotency, and preservation of existing records.

This entry documents the first Claude Code implementation task in the CareerPilot capstone.

## Entry 002 — GitHub Actions CI Pipeline

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented, verified locally, merged into `main` through pull request #1 (merge commit `323acd4`), and passing on GitHub Actions

### Objective

Add an initial continuous integration pipeline that runs backend tests against PostgreSQL 16, lints and builds the frontend, and verifies both Docker images on every push and pull request to `main`, without deploying anything.

### Agent Workflow

1. Claude Code performed a read-only review of backend requirements, pytest fixtures, frontend scripts, Dockerfiles, `docker-compose.yml`, `AGENTS.md`, and `product-spec.md`.
2. The agent identified prerequisites and compatibility issues before implementation:
   - `backend/app/database.py` requires `POSTGRES_*` environment variables at import time; CI has no `.env` file.
   - Plain `pytest` fails with `ModuleNotFoundError: No module named 'backend'`; tests must run as `python -m pytest` from the repository root.
   - `backend/requirements.txt` was encoded as UTF-16 LE, which Git treats as binary.
   - `docker-compose.yml` requires `POSTGRES_*` variables even to parse.
3. The agent proposed a three-job workflow; the developer reviewed and approved it with additional decisions (manual trigger, UTF-8 conversion, documentation).
4. Claude Code implemented the changes and ran local verification without committing or pushing.
5. At the developer's request, Claude Code added a root-level `CLAUDE.md`. It points to `AGENTS.md`, `product-spec.md`, and `openapi.yaml` as primary guidance and documents the architecture, the verified test and build commands, and the rules on secrets, database safety, and human approval.

### Files Changed

- `.github/workflows/ci.yml` — New CI workflow with `backend-tests`, `frontend`, and `docker-build` jobs; triggered by push and pull request to `main` and by `workflow_dispatch`.
- `backend/requirements.txt` — Re-encoded from UTF-16 LE to UTF-8; all 33 pinned versions unchanged.
- `README.md` — Added a CI/CD section.
- `CLAUDE.md` — New root-level Claude Code guidance that references, rather than duplicates, `AGENTS.md`.
- `docs/ai-development-log.md` — Added this entry.

### Safety Decisions

- GitHub token limited to `permissions: contents: read`.
- Temporary CI-only PostgreSQL credentials, scoped to an ephemeral service container; no repository secrets are referenced.
- `careerpilot_test` is created idempotently inside the CI container; the existing `conftest.py` guard still restricts table resets to that database.
- Docker images are built on the runner only; nothing is pushed or deployed.
- Local verification did not connect to or modify the local development or test databases.

### Verification Results (Local)

- Workflow schema validation (`act --validate --strict`): **Passed**
- Workflow job and trigger parsing (`act --list`): **3 jobs, push / pull_request / workflow_dispatch**
- Requirements re-encoding: **33 of 33 entries identical before and after**
- `pip install --dry-run --no-index -r backend/requirements.txt`: **Parsed successfully**
- Backend test collection with CI environment values: **17 tests collected**
- Frontend `npm run lint`: **Passed, no problems**
- Frontend `npm run build`: **Successful**
- `docker compose config --quiet` with dummy values: **Valid**
- Backend and frontend `docker build`: **Successful**
- `CLAUDE.md` commands and architecture details: **Checked against the current repository files and the local results above**

### Verification Results (GitHub Actions)

Confirmed by the developer from GitHub. Workflow: <https://github.com/robanc/CareerPilot/actions/workflows/ci.yml>

- Pull request CI run #1 (pull request #1): **Passed all three jobs**
  - `backend-tests` (backend tests against the CI PostgreSQL 16 service): **Passed**
  - `frontend` (lint and build): **Passed**
  - `docker-build` (backend and frontend images): **Passed**
- Pull request #1 merged into `main`: **Merged** (merge commit `323acd4`)
- Post-merge CI run #2 on `main`: **Completed successfully**

### Verification Pending

- Per-test results from the GitHub-hosted backend job (for example, the number of tests passed): **Not recorded in this log**; the developer confirmed job-level success only.
- Manual `workflow_dispatch` trigger: **Not yet run**

### Human Oversight

The developer approved the plan and its decisions before implementation, reviewed the diff before committing, merged pull request #1, and confirmed the GitHub Actions results.

Claude Code did not commit or push changes without approval.

### Limitations and Follow-Up

- The pipeline does not deploy; deployment is planned for a later stage.
- No frontend tests run in CI yet because Vitest is not configured.
- `pytest` is installed in the production backend image; consider separating development requirements.
- A `StarletteDeprecationWarning` recommends replacing `httpx` with `httpx2` for the test client; it does not fail tests.

### Outcome

CareerPilot has an initial GitHub Actions CI pipeline that has been validated locally and confirmed on GitHub-hosted runners: pull request CI run #1 passed all three jobs, and post-merge CI run #2 on `main` completed successfully.