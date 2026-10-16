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

## Entry 003 — Backend Operating-Mode Configuration

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented and verified locally on branch `feature/render-readonly-demo`; awaiting developer review; not committed

### Objective

Add the initial backend operating-mode configuration for a future read-only public demo: two modes (`local` by default and `public_demo`) selected by `CAREERPILOT_MODE`, with startup refused on Render unless the mode is explicitly `public_demo`.

This is the first step only. Read-only middleware, database restrictions, resume examples, rate limiting, frontend changes, and Render deployment files are explicitly out of scope.

### Agent Workflow

1. The developer supplied a scoped prompt that limited the work to mode configuration, Render fail-closed behavior, and tests, and that prohibited reading `.env`, deploying, committing, or pushing.
2. Claude Code read `CLAUDE.md`, `AGENTS.md`, `backend/app/main.py`, `backend/app/database.py`, and the existing backend tests before editing.
3. Claude Code implemented the settings module, wired it into application startup, and added tests.
4. Claude Code ran the backend test suite, reviewed the diff, and reported risks for developer review.
5. The developer then asked for this log entry.

### Files Changed

- `backend/app/settings.py` — New. Defines the `Mode` enum, the frozen `Settings` object, `SettingsError`, and `load_settings()`. The module docstring documents that `public_demo` is not safe to deploy and that Render detection is unverified.
- `backend/app/main.py` — Startup now loads the settings before `init_db()`, stores them on `app.state.settings`, and logs a warning whenever `public_demo` is active.
- `backend/tests/test_settings.py` — New. 21 tests covering the default, empty, and explicit `local` mode, the explicit `public_demo` mode, invalid values, Render fail-closed behavior, reading from the process environment, and startup being refused on Render.
- `docs/ai-development-log.md` — This entry.

### Safety Decisions

- **Fail closed on Render:** any non-empty `RENDER` value counts as Render, including `"false"`. Wrongly assuming Render only forces an explicit mode, while missing Render would leave a hosted instance in unrestricted `local` mode.
- **Strict mode values:** values must match `local` or `public_demo` exactly (case-sensitive). An unset or empty `CAREERPILOT_MODE` means `local`, so existing Docker Compose and test behavior is unchanged.
- **Validate before the database:** the mode check runs before `init_db()`, so a misconfigured deployment fails without touching the database.
- **No real database in the startup test:** the startup test replaces `init_db` with a stub that fails the test if called, and the unit tests pass explicit environment mappings so the developer's environment cannot affect them.

### Verification Results (Local)

- `python -m pytest backend/tests -q`: **38 passed, 0 failed**, 1 warning (the existing `httpx` deprecation warning)
  - Existing tests preserved: **17 passed**
  - New settings tests: **21 passed**
- `git diff` and `git status` reviewed: only the files listed above changed.

### Verification Pending

- Docker Compose rebuild and run with this change: **Not run**. Compose sets neither `CAREERPILOT_MODE` nor `RENDER`, so it is expected to start in `local` mode.
- GitHub Actions CI: **Not run** (changes are not committed or pushed).
- Render detection through the `RENDER` variable: **Not confirmed** against a real Render service.

### Human Oversight

The developer defined the scope and safety constraints before implementation and requested review before any commit.

Claude Code did not read `.env`, create cloud resources, deploy, commit, or push.

### Limitations and Follow-Up

- **`public_demo` is NOT SAFE TO DEPLOY.** It currently changes nothing except a startup warning. Backend write restrictions, database restrictions, rate limiting, and synthetic-data safeguards must be implemented and tested before any public deployment.
- **Render detection is unverified.** If Render does not set `RENDER`, the guard silently does nothing. Before deployment, confirm the variable in the Render shell and set `CAREERPILOT_MODE=public_demo` explicitly in the service configuration.
- **The check only runs at startup.** Existing tests create `TestClient(app)` without a `with` block, so startup is skipped and `app.state.settings` is not set. Later safeguards that read it must handle this.
- **`.env` can affect the mode.** `database.py` loads `.env` into the environment before startup, so `CAREERPILOT_MODE` or `RENDER` set there would apply locally.
- **Missing database settings fail first.** `database.py` reads the `POSTGRES_*` variables on import, so if they are missing, startup fails with a `KeyError` before the mode check runs. This still fails closed, but with a less clear message.
- **The settings tests need PostgreSQL.** The shared test setup in `conftest.py` resets the `careerpilot_test` database before every test, including these unit tests.

### Outcome

CareerPilot's backend now has a validated operating mode that defaults to `local` and refuses to start on a detected Render host unless `public_demo` is set explicitly. The `public_demo` mode is a placeholder until the read-only safeguards are built.
