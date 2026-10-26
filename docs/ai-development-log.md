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

## Entry 004 — Read-Only HTTP Protection for `public_demo`

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented and verified locally on branch `feature/render-readonly-demo`; awaiting developer review; not committed

### Objective

Make `public_demo` mode reject all write requests at the FastAPI backend, while keeping full CRUD in `local` mode.

Database read-only transactions, demo seeding, rate limiting, frontend changes, and Render deployment configuration are explicitly out of scope.

### Agent Workflow

1. The developer supplied a scoped prompt: a fail-closed method allowlist, an independent route dependency, bypass-resistance, focused tests, and documentation. It prohibited reading `.env`, deploying, committing, or pushing.
2. Claude Code read `CLAUDE.md`, `AGENTS.md`, `backend/app/settings.py`, `backend/app/main.py`, the routers, `frontend/nginx.conf`, `openapi.yaml`, and the existing tests before editing.
3. Claude Code implemented two independent protection layers and added tests.
4. Claude Code ran the full backend suite, then mutation-checked each layer by disabling it and confirming that tests fail.
5. Claude Code reviewed the diff and reported results for developer review.

### Files Changed

- `backend/app/readonly.py` — New. `ReadOnlyMiddleware` (pure ASGI method allowlist), `require_writable` dependency, `is_request_allowed()`, and `current_settings()`.
- `backend/app/main.py` — Registers `ReadOnlyMiddleware` directly inside `CORSMiddleware` (see the CORS correction below) and updates the `public_demo` startup warning.
- `backend/app/routers/applications.py` — Adds `dependencies=[Depends(require_writable)]` to the create, update, and delete endpoints.
- `backend/app/settings.py` — Updates the `public_demo` warning in the module docstring.
- `openapi.yaml` — Documents a `403` `ReadOnly` response on `POST /applications`, `PATCH /applications/{id}`, and `DELETE /applications/{id}`.
- `backend/tests/test_readonly.py` — New. 94 tests: 71 in the initial implementation and 23 added by the CORS correction.
- `docs/ai-development-log.md` — This entry.

### Design and Safety Decisions

- **Fail-closed allowlist, not a blocklist.** In `public_demo`, only `GET`, `HEAD`, and `OPTIONS` pass, plus `POST` to exactly `/resume/match`. Everything else, including `PUT`, `TRACE`, WebDAV methods, and unknown paths, returns `403` with `{"detail": "CareerPilot is running as a read-only public demo; ..."}`.
- **Runs before routing.** The check runs before routing, body parsing, and any database session. A malformed body on a blocked route gets `403`, not `422`. Only `CORSMiddleware` wraps it (see the CORS correction below).
- **Exact path and method matching.** The allowed POST path is compared exactly against the ASGI `scope["path"]`. `/resume/match/`, `//resume/match`, `/resume//match`, `/resume/match%2F`, and case variants are blocked instead of being redirected or normalized. Methods are case-sensitive, so `post` is blocked.
- **Headers are never consulted.** Only the method and path received by the server are used. Neither FastAPI nor Starlette implements method-override headers, and the tests confirm that `X-HTTP-Method-Override`, `X-HTTP-Method`, `X-Method-Override`, `X-Original-Method`, `X-Forwarded-Method`, `X-Original-URL`, `X-Rewrite-URL`, `X-Forwarded-Prefix`, `Forwarded`, and similar headers neither unlock writes nor turn a `GET` into a write. The `_method` query parameter is also ignored.
- **Independent second layer.** `require_writable` runs before `get_db` on every application write endpoint, so writes stay blocked even if the middleware is removed or reordered. A test mounts the applications router on a bare app with no middleware to prove this.
- **Settings resolution.** Both layers read `app.state.settings` (set at startup). If startup has not run (as with `TestClient(app)` without `with`), settings are read from the environment on every request rather than cached. An invalid `CAREERPILOT_MODE` returns `503` instead of falling back to `local`.
- **WebSockets are refused** in `public_demo` (no WebSocket endpoints exist).

### Correction: CORS Handling for a Cross-Origin Frontend

**Follow-up prompt:** The developer noted that the planned production setup is a Render Static Site for the React frontend plus a separate Render FastAPI web service, so browser requests are cross-origin. The developer asked Claude Code to make read-only `403` responses carry correct CORS headers without weakening the allowlist.

**Problem found:** As first implemented, `ReadOnlyMiddleware` was the outermost layer, so its `403` responses never passed through `CORSMiddleware`. A browser on an allowed origin would see an opaque CORS failure instead of the read-only message.

**Change:** In `backend/app/main.py`, the registration order is swapped, so `CORSMiddleware` is now the outermost layer and `ReadOnlyMiddleware` sits directly inside it. Nothing else changed: the allowlist, `require_writable`, the allowed origins, methods, and headers are all the same.

**Why this keeps the allowlist fail-closed:**

- `CORSMiddleware` answers preflights (an `OPTIONS` request carrying both `Origin` and `Access-Control-Request-Method`) itself, without calling the app. `OPTIONS` is on the read-only allowlist anyway.
- Every other request is passed unchanged to `ReadOnlyMiddleware`. `CORSMiddleware` only adds response headers and never alters the method or path.
- **CORS is not authorization.** A successful preflight for `PATCH` or `DELETE` only lets the browser send the request, and that request is still refused with `403`. A disallowed origin gets no `Access-Control-Allow-Origin` header, so the browser cannot read the response. Its writes are refused as well, so CORS is never what blocks a write.
- Preflights that request headers outside `Content-Type` (for example `X-HTTP-Method-Override`) or the method `PUT` are rejected with `400`.

**Origins:** These are unchanged: `http://localhost:5173` and `http://127.0.0.1:5173` (the Vite dev server). There are no wildcards or regexes, and credentials stay disabled. The Docker Compose frontend on port 8080 is same-origin through the nginx `/api/` proxy and needs no CORS. **Production origins are not configured yet.** The plan for a later step is to read an explicit, comma-separated list of exact origins (for example the Render Static Site URL) from an environment variable set in the Render service configuration. Wildcards and `null` must be rejected, and the local origins should stay the default only in `local` mode. Until then, a deployed static site would be refused by CORS, which fails closed.

### Verification Results (Local)

- Initial implementation: `python -m pytest backend/tests -q` gave **109 passed, 0 failed**: 38 existing and 71 new read-only tests.
- After the CORS correction: `python -m pytest backend/tests -q` gave **132 passed, 0 failed**, 1 warning (the existing `httpx` deprecation warning)
  - Previous tests preserved: **109 passed**
  - New CORS tests: **23 passed**. They cover allowed-origin `GET` for both local origins, blocked `POST`/`PATCH`/`PUT`/`DELETE` returning `403` with `Access-Control-Allow-Origin`, allowed-origin `POST /resume/match`, preflights that succeed while the write is still `403`, preflights rejected for `PUT` and for the `X-HTTP-Method-Override`/`X-Original-URL`/`Authorization` headers, four disallowed origins (no CORS headers, preflight `400`, writes still `403`), and local-mode CRUD from an allowed origin.
- Mutation check, middleware disabled (allowlist forced to allow everything): **31 of 71** read-only tests failed, as expected.
- Mutation check, `require_writable` removed from the three routes (temporary source edit, restored afterward): **6 of 71** failed, namely the three router-only tests and the three route-coverage tests, as expected.
- Mutation check, old middleware order restored temporarily (`ReadOnlyMiddleware` outermost): **8 of 132** failed, all of them the "blocked write returns 403 with CORS headers" tests, as expected. Restored afterward.
- `openapi.yaml` parses as valid YAML.
- `git diff` and `git status` reviewed: only the files listed above changed.

### Verification Pending

- Docker Compose run in `public_demo` mode through nginx: **Not run**.
- Frontend lint, build, and behavior in `public_demo`: **Not run** (no frontend changes; the UI will show errors for blocked writes).
- GitHub Actions CI: **Not run** (changes are not committed or pushed).

### Human Oversight

The developer defined the scope and safety constraints before implementation and requested review before any commit.

Claude Code did not read `.env`, deploy, commit, or push.

### Remaining Deployment Blockers

`public_demo` is still **NOT SAFE TO DEPLOY**. Before any public deployment:

- **Resume input is unrestricted.** `POST /resume/match` is allowlisted but has no request size limit, input limits, or abuse protection. It is not yet safe to expose.
- **No database-level protection.** The database user can still write. Read-only transactions or a read-only database role are needed as a further layer.
- **No rate limiting.**
- **No synthetic demo data.** No seeding exists, and nothing prevents a demo instance from pointing at a database with real job-search records.
- **Render detection is unverified** (see Entry 003). Set `CAREERPILOT_MODE=public_demo` explicitly in the service configuration.
- **No Render configuration or frontend read-only UX** yet.
- **Production CORS origins are not configured.** Only the local Vite origins are allowed; see the CORS correction above for the planned environment-variable configuration.
- **`root_path` caveat.** If the backend is later served with a non-empty ASGI `root_path` (for example `uvicorn --root-path`), the exact-path check would block `/resume/match` too. That fails closed, but it would need adjusting. The current nginx setup strips `/api/`, so the backend sees `/resume/match`.
- **`HEAD` and `OPTIONS` are passed to the router.** They are safe today because no handler writes on them; any future handler for those methods must stay read-only.

### Outcome

In `public_demo` mode, the backend now rejects every request outside a narrow read-only allowlist, using two independent layers. `local` mode keeps full CRUD. The demo is still not deployable until the blockers above are resolved.

## Entry 005 — `public_demo` Database Settings Validation (Step 72B)

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented and verified locally on branch `feature/render-readonly-demo`; awaiting developer review; not committed

### Objective

Add the configuration-level groundwork for database-level read-only protection. This is the first increment of the Step 72A design. In that design, `public_demo` connects through a dedicated SELECT-only role, with read-only transactions as a second layer, and administrative credentials never reach the public API process.

> **Database-level enforcement is NOT implemented yet.** This step only validates environment variables at startup. Nothing connects with `CAREERPILOT_DEMO_DATABASE_URL`; `backend/app/database.py` is unchanged and still connects with `POSTGRES_*`. No database role, read-only transaction setting, privilege check, or seeding exists.

### Agent Workflow

1. Step 72A (design only): Claude Code read the guidance files, the backend database, settings, read-only, and startup code, the models, the database tests, the Docker Compose file, and the CI workflow. It then proposed the role-plus-read-only-transaction design. The developer approved implementing only the settings step.
2. The developer's Step 72B prompt prohibited changing `database.py`, creating database roles, connecting to PostgreSQL for this purpose, seeding, deploying, committing, pushing, or reading `.env`.
3. Claude Code changed `settings.py`, added tests, ran the focused and full backend suites, mutation-checked both new rules, and reviewed the diff.

### Files Changed

- `backend/app/settings.py` — In `public_demo`, requires a non-empty `CAREERPILOT_DEMO_DATABASE_URL` and refuses startup if `DATABASE_URL` or `CAREERPILOT_ADMIN_DATABASE_URL` is present. Adds a `Settings.demo_database_url` field, which is excluded from `repr`. Updates the module docstring.
- `backend/tests/test_settings.py` — Updates three existing `public_demo` tests to supply the demo URL. Adds 30 tests.
- `backend/tests/test_readonly.py` — Updates the environment-based `public_demo` test to supply the demo URL and clear the forbidden variables. Adds one test showing a missing demo URL returns `503`.
- `docs/ai-development-log.md` — This entry.

### Design and Safety Decisions

- **Rules apply only in `public_demo`.** In `local` mode (the default, used by Docker Compose and the tests), all three variables are ignored and `demo_database_url` is `None`. `docker-compose.yml` is unchanged.
- **Presence is rejected, not just non-empty values.** `DATABASE_URL` or `CAREERPILOT_ADMIN_DATABASE_URL` set to anything, including an empty string, refuses startup. `DATABASE_URL` is rejected because linking a Render database typically injects the owner connection string under that name (to be verified at deployment).
- **Whitespace-only demo URL is treated as missing.** The value is stripped. Its format is not validated yet; that belongs with the engine change.
- **Order of checks.** The existing mode checks (invalid mode, and Render without `public_demo`) run first, so their errors are unchanged. The forbidden-variable check runs before the demo-URL check, and the error names every forbidden variable that is present.
- **No credential leakage.** Error messages name variables but never include values, and `Settings.__repr__` omits the URL. Tests assert both, using placeholder values on the never-resolving `.invalid` domain.
- **Fail closed at every entry point.** The lifespan raises `SettingsError` before `init_db` runs. If startup is skipped, both read-only layers get `SettingsError` and return `503`; they never fall back to `local`.

### Verification Results (Local)

- `python -m pytest backend/tests/test_settings.py backend/tests/test_readonly.py -q` gave **146 passed, 0 failed**.
- `python -m pytest backend/tests -q` gave **163 passed, 0 failed**, 1 warning (the existing `httpx` deprecation warning). Previously 132; 31 tests are new.
- Mutation check: emptying the forbidden-variable list made **19** tests fail, as expected. Disabling the demo-URL requirement made **7** fail, as expected. `settings.py` was restored from a backup copy after each check.
- `git diff` and `git status` reviewed: only the four files listed above changed.

The full suite uses the existing isolated `careerpilot_test` database, as before. No new database access was added.

### Verification Pending

- GitHub Actions CI: **Not run** (not committed or pushed).
- Docker Compose run: **Not run** (local-mode behavior and Compose configuration are unchanged).
- Render behavior (whether linking a database injects `DATABASE_URL`, and secret environment-variable handling): **Unverified**.

### Human Oversight

The developer approved the Step 72A design and limited this step to settings validation. Claude Code did not read `.env`, change `database.py`, create database roles, seed data, deploy, commit, or push.

### Remaining Deployment Blockers

All blockers from Entry 004 still apply. For database-level protection specifically, the remaining Step 72A work is:

- Mode-aware engine creation in `database.py` that uses `CAREERPILOT_DEMO_DATABASE_URL` in `public_demo`.
- The SELECT-only role, read-only transactions on the connection, and a startup privilege check.
- `public_demo` startup that skips `create_all`.
- An admin bootstrap and insert-only seed tool, run from the developer's machine.
- Database-level write-rejection tests against `careerpilot_test`.

`public_demo` remains **NOT SAFE TO DEPLOY**.

### Outcome

A `public_demo` process now refuses to start unless it has a dedicated demo database URL and no owner or admin database URL. This is configuration groundwork only; the database itself is not yet read-only.

## Entry 006 — Mode-Aware Lazy Database Engine (Step 72F)

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented and verified locally on branch `feature/render-readonly-demo`; awaiting developer review; not committed

### Objective

Make `backend/app/database.py` choose its connection by operating mode, and create the engine lazily instead of at import. This is the next increment of the Step 72A design, following the settings validation in Entry 005.

> **Database-level read-only enforcement is NOT implemented yet.** This step only controls *which* credentials the backend connects with. No PostgreSQL role has been created, no grants have been changed, read-only transactions are not set on the connection, and there is no startup privilege check. If `CAREERPILOT_DEMO_DATABASE_URL` held owner credentials, the database would still accept writes. `public_demo` remains **NOT SAFE TO DEPLOY**.

### Agent Workflow

1. The developer's Step 72F prompt limited the work to mode-aware, lazy engine and session configuration. It prohibited creating database roles, changing grants, seeding, changing Docker Compose, deploying, committing, pushing, reading `.env`, and running tests against any non-test database.
2. Claude Code read `CLAUDE.md`, `AGENTS.md`, `database.py`, `settings.py`, `main.py`, `readonly.py` (state lookup only), `conftest.py`, and the existing database, settings, and read-only tests.
3. Claude Code implemented the change, added tests, ran mutation checks, ran the focused and full backend suites, and reviewed the diff.

### Files Changed

- `backend/app/database.py` — Removes the import-time `DATABASE_URL`, `engine`, and `SessionLocal`. Adds `local_database_url()` (POSTGRES_*, same defaults as before), `public_demo_database_url()` (parses and validates the demo URL), `database_url_for()`, `create_engine_for()`, and the lazy accessors `get_engine()`, `get_session_factory()`, and `reset_engine()`. `get_db()` and `init_db()` now use the lazy engine.
- `backend/app/settings.py` — Docstring only: no longer says `database.py` uses POSTGRES_* in `public_demo`.
- `backend/tests/conftest.py` — Builds the test URL with `local_database_url()` instead of the removed `DATABASE_URL` constant. The database name is still forced to `careerpilot_test` and the existing guard assertion is unchanged. Resets the lazy engine after each test.
- `backend/tests/test_database_engine.py` — New: 28 tests.
- `docs/ai-development-log.md` — This entry.

### Design and Safety Decisions

- **No engine at import.** Importing `database.py` or the app builds no engine. The first `get_engine()` call (from `init_db()` at startup, or `get_db()` on a request) builds it. `create_engine` does not connect; the first connection happens when a session or `create_all` uses it.
- **`local` mode is unchanged.** It uses the same POSTGRES_* variables, the `127.0.0.1:5432` defaults, `postgresql+psycopg`, `pool_pre_ping=True`, and `autoflush=False`. One engine and one session factory are reused. A missing `POSTGRES_USER`, `POSTGRES_PASSWORD`, or `POSTGRES_DB` now raises a `SettingsError` that names the variable when the engine is first needed, instead of a `KeyError` at import.
- **`public_demo` uses only `Settings.demo_database_url`.** POSTGRES_* are ignored even when set, and are not required. There is no fallback path: when settings validation fails (a missing demo URL, or `DATABASE_URL` / `CAREERPILOT_ADMIN_DATABASE_URL` present), no engine is created.
- **Demo URL validation (fail closed).** The URL must parse, use `postgresql://` or `postgresql+psycopg://` (it is normalized to `postgresql+psycopg`), and include a username, host, and database name. Query options such as `sslmode` are kept. Other drivers, such as SQLite, MySQL, and asyncpg, are rejected.
- **No credential leakage.** Error messages name `CAREERPILOT_DEMO_DATABASE_URL` but never include its value. The SQLAlchemy parser error is suppressed with `from None`, because its message can quote the raw URL.
- **Engine always matches current settings.** Settings are re-read on each `get_engine()` call. If they differ from the cached engine's, the engine is disposed and replaced, so a `public_demo` process can never reuse an engine built in `local` mode. Settings validation runs first on every call, so a configuration that became invalid fails immediately.
- **Not addressed here.** `init_db()` still runs `create_all` at startup in `public_demo`, now through the demo URL. Skipping it in `public_demo` is a planned Step 72A item. The tool cannot detect whether the demo URL actually holds owner credentials; that requires the role and privilege check.

### Test Isolation

- All new tests use placeholder URLs on the never-resolving `.invalid` domain and never open a connection. The only real database the suite touches is still `careerpilot_test`, through the existing `conftest.py` engine and guard.
- The import test runs in a separate interpreter with `sqlalchemy.create_engine` replaced by a function that exits the process, then confirms that importing the app in `public_demo` creates no engine.
- **Correction during development:** the first full-suite run had 1 failure (`test_init_db_preserves_existing_rows` got `403` instead of `201`). The new startup test runs the lifespan in `public_demo`. The lifespan stores `public_demo` settings on `app.state` before `init_db` fails, and those settings stayed in place, so later tests became read-only. The test now restores `app.state.settings` afterwards. The application code was not changed for this.

### Verification Results (Local)

- `python -m pytest backend/tests/test_database_engine.py -q` gave **28 passed, 0 failed**.
- `python -m pytest backend/tests -q` gave **191 passed, 0 failed**, 1 warning (the existing `httpx` deprecation warning). Previously 163; 28 tests are new.
- Mutation checks (`database.py` restored from a backup copy after each one, and the restore confirmed with `cmp`):
  - Building an engine at import made the import test fail.
  - Using POSTGRES_* in `public_demo` made 15 tests fail.
  - Caching the first engine regardless of mode made the mode-switch test fail.
  - Chaining the parser error (removing `from None`) made 2 tests fail.
- `git diff` and `git status` reviewed: only the five files listed above changed.

### Verification Pending

- GitHub Actions CI: **Not run** (not committed or pushed).
- Docker Compose run: **Not run** (Compose is unchanged; local mode uses the same variables).
- Connecting with a real demo role: **Not done** (no role exists yet).

### Human Oversight

The developer limited this step to engine and session selection. Claude Code did not read `.env`, create database roles, change grants, seed data, change Docker Compose, deploy, commit, or push.

### Remaining Deployment Blockers

All blockers from Entries 004 and 005 still apply, except mode-aware engine creation. The remaining Step 72A database work is:

- The SELECT-only PostgreSQL role and its grants.
- Read-only transactions on `public_demo` connections, and a startup privilege check.
- `public_demo` startup that skips `create_all`.
- An admin bootstrap and insert-only seed tool, run from the developer's machine.
- Database-level write-rejection tests against `careerpilot_test`.

`public_demo` remains **NOT SAFE TO DEPLOY**.

### Outcome

The backend now creates its database engine lazily. In `local` mode it connects with POSTGRES_* exactly as before. In `public_demo` it connects only with the validated `CAREERPILOT_DEMO_DATABASE_URL` and fails closed otherwise. The database itself is not yet read-only.

## Entry 007 — Read-Only Sessions and public_demo Schema Check (Step 73B)

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented and verified locally on branch `feature/render-readonly-demo`; awaiting developer review; not committed

### Objective

Implement the code-only part of the Step 73A preflight design: read-only database sessions for `public_demo`, no `create_all` in `public_demo` startup, and a stronger live guard before destructive test cleanup.

> **The dedicated SELECT-only PostgreSQL role is NOT implemented, and there are no real-database tests of write rejection by role privileges.** Read-only transactions are defense-in-depth, not a privilege boundary: a client that can run SQL can `SET` them off. If `CAREERPILOT_DEMO_DATABASE_URL` held owner credentials, the database would still allow writes after such a `SET`. `public_demo` remains **NOT SAFE TO DEPLOY**.

### Agent Workflow

1. Step 73A was an inspection-only preflight. It produced a design that the developer approved, and the code-only portion was scoped as Step 73B.
2. The Step 73B prompt prohibited creating roles, changing PostgreSQL permissions, seeding, deploying, committing, pushing, reading `.env`, and running SQL against any non-test database.
3. Claude Code read `CLAUDE.md`, `AGENTS.md`, `database.py`, `main.py`, `settings.py`, `conftest.py`, and the existing database tests. It then implemented the change, added tests, ran mutation checks and the focused and full suites, and reviewed the diff.

### Files Changed

- `backend/app/database.py` — `create_read_only_engine()` is used only in `public_demo`. It sends the libpq startup options `-c default_transaction_read_only=on -c statement_timeout=5000` and registers a connect hook, `verify_read_only_session()`. Also adds `verify_schema()`, and `init_db()` now refuses to run in `public_demo`. Adds `ReadOnlySessionError` and `SchemaError`.
- `backend/app/main.py` — In `public_demo` the lifespan calls `verify_schema()` instead of `init_db()`, and the startup warning is updated. Local startup is unchanged.
- `backend/app/settings.py` — Docstring only.
- `backend/tests/db_safety.py` — New: `require_test_database()` and `reset_test_schema()`.
- `backend/tests/conftest.py` — The per-test reset now uses `reset_test_schema()`. The existing URL-name assertion is kept unchanged.
- `backend/tests/test_database_init.py` — The direct `drop_all` now runs after the live check, on the same connection.
- `backend/tests/test_database_engine.py` — Docstring only.
- `backend/tests/test_database_readonly_session.py` — New: 25 tests.
- `backend/tests/test_db_safety.py` — New: 16 tests.
- `docs/ai-development-log.md` — This entry.

### Design and Safety Decisions

- **public_demo only.** Local mode still builds `create_engine(url, pool_pre_ping=True)` with no options and no hook. Local CRUD and `init_db()` are unchanged.
- **The URL cannot disable read-only.** SQLAlchemy applies `connect_args` after the URL's query parameters. A demo URL containing `?options=-c default_transaction_read_only=off` is overridden, while other query options such as `sslmode` are kept.
- **Verified on every new connection (fail closed).** The connect hook reads `pg_settings` and closes the connection, raising `ReadOnlySessionError`, unless `default_transaction_read_only` is `on` and `statement_timeout` is `5000`. This catches a server or pooler that ignores startup options. The error names the setting only, never the URL.
- **`statement_timeout` = 5 s** limits slow or abusive queries, such as `pg_sleep`. It is not rate limiting.
- **No `create_all` in public_demo.** `verify_schema()` only inspects the catalog. A missing table raises `SchemaError` without retrying, so startup fails closed. Connection errors are retried as in `init_db()`. As defense-in-depth, `init_db()` raises `SettingsError` in `public_demo` even if it is called directly with a `bind`.
- **Live test-database guard.** `reset_test_schema()` opens one connection and one transaction. In that transaction it checks the configured name, then checks the live `SELECT current_database()` for an exact, case-sensitive `str` match on `careerpilot_test`, and only then runs `drop_all`/`create_all`. The check and the cleanup cannot target different databases. The guard uses explicit raises, not `assert`, so it survives `python -O`. Any error during the check propagates, so cleanup never runs, and there is no skip or override switch.

### Test Isolation

- Unit tests use placeholder URLs on the never-resolving `.invalid` domain. The DBAPI `connect` call, DBAPI connections, the schema inspector, and `create_all` are replaced with fakes, so no external or development database is contacted.
- **One real-database test:** `test_read_only_session_rejects_writes_on_test_database` builds a read-only engine for `careerpilot_test` with the test (owner) credentials. It passes the live guard, confirms that `transaction_read_only` is `on` and `statement_timeout` is `5s`, and confirms that PostgreSQL 16 rejects `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, and `CREATE TEMP TABLE` with "read-only transaction". It proves the session settings work on a real server and that the connect hook accepts the real `pg_settings` values. It does **not** prove anything about role privileges.

### Verification Results (Local)

- Baseline before changes: `python -m pytest backend/tests -q` gave **191 passed**.
- Focused: `test_database_readonly_session.py`, `test_db_safety.py`, `test_database_init.py`, and `test_database_engine.py` gave **71 passed, 0 failed** before the integration test was added. `test_database_readonly_session.py` gave **25 passed** after it was added.
- Full suite: `python -m pytest backend/tests -q` gave **232 passed, 0 failed**, 1 warning (the existing `httpx` deprecation warning). 41 tests are new.
- `python -O -m pytest backend/tests/test_db_safety.py -q` gave **16 passed**, so the guard does not depend on `assert`.
- Mutation checks (each file restored from a backup and confirmed with a byte comparison). Each mutation made the full suite fail:
  - Removing the startup options: 4 failed.
  - Removing the connect hook: 1 failed.
  - Calling `init_db()` in public_demo startup: 3 failed.
  - Removing the `init_db()` public_demo guard: 2 failed.
  - Ignoring missing tables: 2 failed.
  - Ignoring wrong session settings: 5 failed.
  - Removing the live `current_database()` check: 13 failed.
  - Running `drop_all` before the check: 3 failed.
- `git diff` and `git status` reviewed.

### Verification Pending

- GitHub Actions CI: **Not run** (not committed or pushed).
- Docker Compose run: **Not run** (local mode is unchanged).
- Render: whether its connection path accepts libpq `options` is **unverified**. If it does not, the connect hook makes `public_demo` refuse every connection; it fails closed and never silently continues.

### Human Oversight

The developer approved the Step 73A design and limited this step to code. Claude Code did not read `.env`, create roles, change grants or database permissions, seed data, change Docker Compose or CI, deploy, commit, or push. The only database it connected to was `careerpilot_test`, through the existing test credentials.

### Remaining Deployment Blockers

- **The dedicated SELECT-only role is pending.** That covers the role setup script, grants, `ALTER DEFAULT PRIVILEGES`, `REVOKE TEMPORARY ... FROM PUBLIC` on `careerpilot_test`, and the CI setup step. All of it needs developer approval before any PostgreSQL state changes (see the Step 73A preflight).
- **Real write-rejection tests by role privileges against `careerpilot_test` are pending.** These include ownership, membership, and superuser checks.
- A startup privilege check that the demo role cannot write.
- An admin bootstrap and insert-only seed tool, plus rate limiting, resume input limits, and synthetic-data safeguards, as listed in earlier entries.

`public_demo` remains **NOT SAFE TO DEPLOY**.

### Outcome

`public_demo` connections are now read-only with a 5-second statement timeout, and this is verified on every connection. `public_demo` startup never creates tables and fails closed if the schema is missing. Destructive test cleanup now requires the live database to be exactly `careerpilot_test`. Local mode is unchanged.

## Entry 008 — Test-Reader Role Provisioning and Privilege Tests (Steps 73C–73C-10)

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented and verified locally on branch `feature/render-readonly-demo`; awaiting developer review; not committed

### Objective

Provision a SELECT-only, NOLOGIN PostgreSQL role, `careerpilot_test_reader`, in `careerpilot_test`. Then prove with real-database tests that its privileges allow SELECT and reject writes.

> **This tests role privileges, not a login security boundary.** The tests enter the role with `SET LOCAL ROLE` from the superuser test connection, so `session_user` stays the superuser, which could `RESET ROLE`. The public demo role, its login, and its containment are still pending. `public_demo` remains **NOT SAFE TO DEPLOY**.

### Agent Workflow

1. Claude Code reviewed and corrected the provisioning scripts `backend/tests/sql/01_test_reader_role.sql` and `02_test_reader_grants.sql`. It ran no SQL itself.
   - Step 73C-5: the final `pg_shdepend` post-check skipped `dbid 0`, which hid grants on shared objects (databases, tablespaces, parameters). It was replaced with an allowlist: every reference to the reader must be an ACL entry, created by the script, in `careerpilot_test`. Claude Code also added default-privilege and grant-option checks.
   - Step 73C-7: the developer's first run of script 02 failed before COMMIT with `"pg_statistic" is not a sequence`, so nothing was applied. SQL does not guarantee the order in which `WHERE` conditions are evaluated, so `has_sequence_privilege` was called on a non-sequence. The check now runs in a PL/pgSQL loop over rows already selected as sequences. A NULL result fails closed.
2. **The developer provisioned the role** (Claude Code did not). Script 01 succeeded and the role attributes were verified. Script 02 then succeeded. The developer's independent privilege checks returned `t|t|f|f|f|f`: database identity, SELECT, write, TEMP, CREATE, and sequence access.
3. Step 73C-9: Claude Code added automated tests, then ran mutation checks, the focused tests, and the full suite.
4. Step 73C-10: Claude Code added a CI step that provisions the role before pytest. It did not run the step or the scripts locally.

### Files Changed

- `.github/workflows/ci.yml` — New step in the `backend-tests` job: **Provision careerpilot_test_reader role**.
- `backend/tests/sql/01_test_reader_role.sql`, `backend/tests/sql/02_test_reader_grants.sql` — New provisioning scripts (corrected in Steps 73C-5 and 73C-7).
- `backend/tests/test_test_reader_role.py` — New: 10 tests.
- `docs/ai-development-log.md` — This entry.

### Test Design

- **Dedicated `NullPool` engine** on the test engine's URL, so a role-switched connection is never reused. It is disposed after each test.
- **One connection, one transaction:** `require_test_database()` runs first. Next, a fixed query checks that the role exists, and the test fails with provisioning instructions if it does not. Then `SET LOCAL ROLE careerpilot_test_reader` runs, and `current_user` is checked. Every probe statement runs only after that, as the reader. The superuser session runs only these fixed checks, never application SQL.
- **Always rolled back**, in a `finally`, including when a probe that should fail succeeds.
- **Identity and attributes:** `current_database()` is `careerpilot_test`, `current_user` is the reader, and `session_user` is not. The role has none of the attributes `rolsuper`, `rolcanlogin`, `rolinherit`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, or `rolbypassrls`. It has a connection limit of 0, no memberships, and no `pg_read_all_data`/`pg_write_all_data` membership.
- **SELECT works** on a synthetic row seeded by the owner. The tables are recreated before every test, so this also exercises `ALTER DEFAULT PRIVILEGES`.
- **Rejected with SQLSTATE `42501`**, each test in its own transaction: `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `CREATE TABLE`, `CREATE TEMP TABLE`, and `nextval` on the `job_applications` id sequence. After the rollback, the owner confirms that the row count is unchanged and that no probe table exists.
- **No skips.** A missing role or a wrong privilege fails the test.

### Verification Results (Local)

- Focused: `python -m pytest backend/tests/test_test_reader_role.py -v` gave **10 passed**.
- Full suite: `python -m pytest backend/tests -q` gave **242 passed, 0 failed**, 1 warning (the existing `httpx`/starlette deprecation warning). The 10 tests are new; the previous total was 232.
- Mutation checks, each run on a temporary copy of the test file that was deleted afterwards:
  - A nonexistent role name: 10 failed, each with the provisioning message.
  - `SET LOCAL ROLE` and the `current_user` check removed: 9 failed (identity, attributes, and all 7 rejections). Only the SELECT test passed, as expected.
  - Afterwards, `to_regclass('public.reader_probe')` on `careerpilot_test` was `NULL`, so the rollback held even when writes succeeded.

### CI Provisioning (Step 73C-10)

- **Placement:** the new step runs after **Create careerpilot_test database (idempotent)** and before **Run pytest**.
- **How it runs:** it executes `01_test_reader_role.sql`, then `02_test_reader_grants.sql`, each with `psql -X -v ON_ERROR_STOP=1 -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d careerpilot_test -f backend/tests/sql/<script>`.
- **No `--single-transaction`:** the scripts have their own `BEGIN`/`COMMIT`.
- **Credentials:** the step uses the existing CI service credentials (`careerpilot_ci`, which is the service superuser, and `PGPASSWORD` from the job `env`). It adds no secrets and prints no passwords.
- **Fail fast:** `set -eu` and `ON_ERROR_STOP` stop the step at the first error. A failed step skips **Run pytest**, so the job fails.
- **Why the scripts' pre-checks hold in CI:** `createdb` runs as `careerpilot_ci`, so it owns `careerpilot_test`. The database is empty, so script 02's ownership checks pass, `GRANT ... ON ALL TABLES` grants nothing, and the default privileges cover the tables pytest creates as `careerpilot_ci`.
- **No other changes:** the other steps and jobs are unchanged.
- **Local checks only:** the workflow parsed with PyYAML (`yaml.safe_load`), and the step order was confirmed. The diff was reviewed. `actionlint` is not installed, so it was not run.

### Verification Pending

- **The CI provisioning step has NOT been executed.** Nothing is committed or pushed, so GitHub Actions has not run. Everything in "Verification Results (Local)" ran only on the developer's machine, against a role the developer provisioned by hand.
- **The SQL scripts are untracked.** `backend/tests/sql/` must be committed together with the workflow change, or the step fails because the files are missing.
- **Expected in the first CI run:** the provisioning step succeeds, and pytest reports 242 passed. This is not yet confirmed.

### Human Oversight

The developer ran both provisioning scripts and the independent privilege checks. Claude Code did not create or alter roles, change grants, run the provisioning SQL (locally or through the new CI step), read `.env`, connect to the development database, commit, push, or deploy. Its only database connections were to `careerpilot_test`, through the existing test credentials.

### Remaining Deployment Blockers

- The public demo login role, with its own credentials and real login containment, plus a startup privilege check that it cannot write.
- A successful GitHub Actions run of the new CI provisioning step and the full suite.
- The items still open from Entry 007: the admin bootstrap and insert-only seed tool, rate limiting, resume input limits, and synthetic-data safeguards.

`public_demo` remains **NOT SAFE TO DEPLOY**.

### Outcome

`careerpilot_test_reader` is provisioned locally. Automated tests now prove, against real PostgreSQL 16, that it can SELECT and that PostgreSQL rejects every tested write, DDL, TEMP, and sequence operation with `42501`.

## Entry 009 — public_demo Startup Privilege Verification (Step 73D-1)

**Date:** October 16, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented and verified locally on branch `feature/render-readonly-demo`; awaiting developer review; not committed

#### Manual security review follow-up

- Reviewed the startup privilege verification and PostgreSQL catalog queries.
- Strengthened `DEMO_COLUMN_GRANTS_QUERY` to use effective PostgreSQL column privilege checks across relations.
- Added a narrow exception for PostgreSQL's built-in `pg_catalog.pg_settings` UPDATE privilege.
- Added a regression test protecting the exception and other column privilege checks.
- Verified against the existing PostgreSQL 16 test reader.
- Final validation: 314 backend tests passed, 1 existing deprecation warning.
- No database roles, grants, credentials, or deployment configuration were modified.
- `public_demo` remains NOT SAFE TO DEPLOY.

### Objective

Phase 1 of the approved Step 73D design: at `public_demo` startup, verify through the configured demo connection itself that the connected role is strictly SELECT-only, and refuse to start otherwise. Phases 2–5 (the LOGIN test role, Render provisioning scripts, bootstrap and seed, and deployment) were not started.

> **The demo role's actual privileges are the security boundary.** The read-only session settings are defense-in-depth, because a client can `SET` them off. This step only *verifies* privileges. No demo LOGIN role exists yet, and `public_demo` remains **NOT SAFE TO DEPLOY**.

### Files Changed

- `backend/app/database.py`:
  - Adds `DemoPrivilegeError`, `demo_privilege_problems(connection)`, and `verify_demo_role_privileges()`. The queries are named constants.
  - The `public_demo` engine now has a small, provisional pool: `pool_size=2`, `max_overflow=1`, `pool_timeout=10`, `pool_recycle=1800`.
  - Module docstring updated.
- `backend/app/main.py` — `public_demo` startup now calls `verify_demo_role_privileges()` after `verify_schema()`, and the startup warning is updated. Local startup is unchanged.
- `backend/app/settings.py` — Docstring only.
- `backend/tests/test_demo_role_privileges.py` — New: 71 tests.
- `backend/tests/test_database_readonly_session.py` — **Outside the step's listed scope; one-line change.** `test_public_demo_startup_verifies_schema_without_create_all` now stubs the new check. Without the stub, startup tries to connect to the placeholder `demo-db.invalid` host and the test fails.
- `docs/ai-development-log.md` — This entry.

### What the Check Verifies

It runs on the demo engine from `get_engine()`, never on an owner or superuser connection. It uses only `SELECT` statements against catalogs and privilege functions: no test writes, DDL, `SET ROLE`, or grants.

- **Identity:** `session_user = current_user`. The role has none of SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, or BYPASSRLS, and it is not a member of any role.
- **Ownership:** it owns no database, schema, or relation. A count from `pg_shdepend` also catches owned objects of any type in any database.
- **Database:** it has neither `CREATE` nor `TEMPORARY`.
- **Schemas:** it has `CREATE` on none. It has `USAGE` on each schema the application tables use.
- **Application tables:** it has `SELECT`. It has none of `SELECT WITH GRANT OPTION`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, or `TRIGGER`. Column-level grants are checked too, through `has_any_column_privilege`.
- **Every relation in the database:** no write privilege or grant option at table level, and no column-level grant other than plain SELECT, whether granted to the role or to PUBLIC.
- **Sequences:** the sequences are listed first, and then `has_sequence_privilege` is called once per sequence, so it never runs against a non-sequence (the Step 73C-7 evaluation-order bug). Any `USAGE`, `SELECT`, or `UPDATE` fails the check.
- **Fail closed:** any value other than an explicit `false` (including `NULL`) counts as granted. All problems are reported together in one `DemoPrivilegeError`. Long lists are truncated.
- **No secrets in error messages:** messages never include the URL, host, password, the connected role's name, or the current database's name, which is shown as `(current)`.
- **Retries:** connection errors are retried as in `verify_schema`.
- **Checked once at startup:** grants changed afterwards are not detected until the next restart.

### Finding From the Real-Database Test

The first run as the NOLOGIN test reader flagged `pg_catalog.pg_settings`. PostgreSQL grants `UPDATE` on that view to PUBLIC by default, and updating it is equivalent to `SET` for the current session. That is exactly that one privilege on exactly that view, so it is now exempted, and every other privilege on `pg_settings` is still checked. A test pins this down.

### Verification Results (Local)

- Focused: `python -m pytest backend/tests/test_demo_role_privileges.py -q` gave **71 passed**.
  - 69 tests use fake connections. They cover a negative case for every role attribute, membership, each ownership kind, database `CREATE`/`TEMPORARY`, schema `CREATE`/`USAGE`, each table-level and column-level privilege, the any-relation and column-ACL sweeps, and each sequence privilege. They also cover `NULL` failing closed, retries, no secrets in messages, the startup order (schema, then privileges), startup refusal, local startup skipping the check, and the pool settings.
  - 2 tests run on real PostgreSQL 16 in `careerpilot_test`:
    - As `careerpilot_test_reader` via `SET LOCAL ROLE` (in the test only, always rolled back), the check reports exactly one problem: the `SET ROLE` detection.
    - With the owner/superuser test credentials, the check rejects SUPERUSER, ownership, and `INSERT` on `job_applications`.
- Full suite: `python -m pytest backend/tests -q` gave **313 passed, 0 failed**, 1 warning (the existing `httpx`/starlette deprecation warning). The previous total was 242.
- Mutation checks, each restored from a backup and confirmed with `cmp`. Each one made the focused tests fail:
  - Startup call removed: 2 failed.
  - Treating `NULL` as not granted: 19 failed.
  - Sequence check skipped: 5 failed.
  - `SET ROLE` check removed: 2 failed.
  - Never raising: 56 failed.

### Verification Pending

- GitHub Actions CI: **Not run** (not committed or pushed). The two real-database tests depend on `careerpilot_test_reader`, which CI already provisions (Step 73C-10).
- No demo LOGIN role exists, so no real login has passed the check yet. That is Phase 2.

### Human Oversight

Claude Code did not edit the SQL provisioning scripts, create or modify roles, run provisioning SQL, read `.env`, connect to the development database, commit, push, or deploy. Its database access was limited to `careerpilot_test`, through the existing test credentials. It ran only read-only catalog queries, plus `SET LOCAL ROLE` in a rolled-back transaction in one test. Note: the owner test's catalog query lists every database the test superuser owns, so the development database's *name* appeared in local test output. No connection was made to it.

### Remaining Deployment Blockers

- Phases 2–5 of the Step 73D design: the LOGIN test role and real-login tests, the Render provisioning scripts and runbook, the admin bootstrap and fictional seed, and deployment.
- Rate limiting, resume input limits, and synthetic-data safeguards.
- The pool limits are provisional and depend on the Render plan, the role's `CONNECTION LIMIT`, and the worker count.

`public_demo` remains **NOT SAFE TO DEPLOY**.

### Outcome

`public_demo` now refuses to start unless the connected database role is strictly SELECT-only. The check runs through the real demo connection and fails closed on any unexpected attribute, membership, ownership, or privilege.

## Entry 010 — Isolated PostgreSQL Test Container (Step 73D-2 Stage A)

**Date:** October 19, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Files written on branch `feature/render-readonly-demo`; Tier 1 and Tier 2 checks passed locally (314 tests passed against the isolated container); `ops/test-backend.ps1` then received a safety patch that passed its Tier 1 read-only checks and its Tier 2 verification (314 passed; port refusal confirmed). Committed as `64f42b0` and pushed to PR #2; GitHub Actions run `39286486531` succeeded, with all three jobs `success`, including `backend-tests` (26 s, confirmed visually by the developer); see "GitHub Actions (PR #2)". That CI record was committed as `0ace3a3`, whose own run `39289469411` also succeeded, with all three jobs `success`. This second-run note is not yet committed

### Objective

Stage A of the approved Step 73D-2 v3 design: move backend testing to a dedicated, disposable PostgreSQL 16 container, so a future test LOGIN role (`careerpilot_test_demo_login`) never exists in the cluster that holds development data. Locally the development container stays unchanged. In CI, the same container replaces the GitHub Actions service container.

Stage A only adds the container and how it is started. It creates no LOGIN role. Stages B–E (scripts 03–05, the ephemeral-password fixture, real-login and negative tests, docs) were not started.

### Why a Separate Container

- **Locally:** it is the only way to keep a LOGIN role out of the cluster with development data, without editing that cluster's `pg_hba.conf` or PUBLIC grants (both rejected in review).
- **In CI:** the old service container already isolated *data* (ephemeral, no real data). But its `pg_hba.conf` cannot be controlled: service containers start before checkout and cannot override the command. So per-database restriction and SCRAM-only login could not be enforced there. Using the same Compose file in both places gives identical behaviour, with fewer CI steps than before.

### Files Changed

- `docker-compose.test.yml` — **New.** Project `careerpilot-test`, service `db-test`, `postgres:16-alpine`.
  - The data directory is tmpfs.
  - It listens on `127.0.0.1:5433`.
  - `-c hba_file=/etc/careerpilot/pg_hba.conf` and `-c cluster_name=careerpilot-test`.
  - `backend/tests/sql` is mounted read-only as the image's init directory.
  - The healthcheck uses `pg_isready` over TCP.
  - Credentials are fixed, non-secret test values, and the file has no `${...}` interpolation.
- `backend/tests/postgres/pg_hba.conf` — **New.** In order:
  1. three lines for `careerpilot_test_demo_login` (reject over the socket, SCRAM over TCP into `careerpilot_test` only, reject everything else)
  2. `local all all trust`
  3. `host all all all scram-sha-256`

  Replication connections match no line, so they are rejected.
- `.gitattributes` — **New** (none existed). LF line endings for `backend/tests/sql/*.sql` and the new `pg_hba.conf`, which are mounted into a Linux container.
- `ops/test-backend.ps1` — **New.** Windows helper:
  - starts or reuses the container with `up --detach --wait`
  - sets `POSTGRES_*` for one pytest run
  - restores the previous values in `finally`
  - runs fail-closed safety checks before startup, after startup, and before pytest (added by the safety patch; see below)
- `.github/workflows/ci.yml` — `backend-tests` job only:
  - **removed:** the `services: postgres` block, `PGPASSWORD`, **Create careerpilot_test database (idempotent)**, and **Provision careerpilot_test_reader role**
  - **added:** **Start isolated test PostgreSQL** (`docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait`) and a **Show test PostgreSQL logs** step that runs only on failure
  - `POSTGRES_*` now hold the test container's values, with port 5433
  - **Run pytest** and the frontend and docker-build jobs are unchanged
- `docs/ai-development-log.md` — This entry.

**Unchanged:** `01_test_reader_role.sql`, `02_test_reader_grants.sql`, `docker-compose.yml`, `conftest.py`, `db_safety.py`, and all application code. Local mode and `public_demo` behaviour are unchanged.

### Design Notes

**PostgreSQL 16 initialization with the custom `pg_hba.conf`.** This reasoning comes from the official image's entrypoint and was confirmed locally by the Tier 2 container log (below):
- The entrypoint passes the container command's arguments, including `-c hba_file=...`, to its temporary initialization server. That server listens only on the Unix socket.
- Initialization runs `psql --no-password` over that socket as the test superuser. The `local all all trust` line is what allows it. The role-specific `local ... reject` line affects only `careerpilot_test_demo_login`, which does not exist yet.
- The entrypoint appends its own `host all all all scram-sha-256` line to `$PGDATA/pg_hba.conf`. That file is not used, because `hba_file` points elsewhere.
- The image creates `careerpilot_test` as the test superuser, then runs `01` and `02` against it. Their pre-checks hold:
  - the current database is `careerpilot_test`
  - `current_user` is a superuser and owns the database
  - `public` is owned by `pg_database_owner`
  - no relations exist yet
- The TCP healthcheck fails while only the socket server is running, so `--wait` returns only after initialization has finished.

**Isolation of the Compose project from development:**
- Separate project name: `name:` in the file, and `-p careerpilot-test` on every command, which also overrides any `COMPOSE_PROJECT_NAME`.
- Separate service name, no `container_name`, no external networks, and no named volumes.
- tmpfs data: a restart or `down` discards everything.
- Separate host port.
- No interpolation from `.env`.

**`ops/test-backend.ps1` safety:**
- **Exactly one pytest target.** `-Path` defaults to `backend/tests`. A single file or `file::test` node replaces it rather than being added to it. The path must exist and be inside `backend/tests`.
- **Unknown arguments are rejected.** `[CmdletBinding()]` means anything other than `-Path` causes an error, so nothing is passed through to pytest by accident.
- **Dot-sourcing is refused.** In the caller's scope, `exit` would close the interactive shell. When the script runs normally, `exit` ends only the script.
- **`$ErrorActionPreference = 'Continue'`.** Windows PowerShell 5.1 can turn docker's stderr progress into a terminating error under `Stop`, so exit codes are checked explicitly instead.
- **Environment restore.** The previous `POSTGRES_*` values (or their absence) are restored in `finally`, which PowerShell also runs on Ctrl+C.
- **No values printed.** It never reads `.env` and prints no values.

**`ops/test-backend.ps1` safety patch (after Tier 2, developer-requested):** the checks only read Docker and port state; they never stop, change, or remove anything. Any failure throws, the run is refused with exit code 3, and the `finally` block still restores `POSTGRES_*`. Docker state is read as `docker inspect` JSON and parsed with `ConvertFrom-Json`, because Windows PowerShell 5.1 strips the inner quotes of `--format` templates (seen in Tier 2).
- **Before startup:**
  - The `careerpilot-test` project may contain at most one container, with service label `db-test`. Any other container in the project refuses the run.
  - The project may have no volumes, and no network other than `careerpilot-test_default`.
  - No container outside the project may be *running* with a host port binding on 5433. A *stopped* one (such as `pipeline-kestra_postgres-1`, found in Tier 2) only produces a warning, because it cannot hold the port.
  - No process may listen on 5433 (checked with `Get-NetTCPConnection`) unless this project's own container is already running with that binding. Otherwise the run is refused, naming the owning process and PID.
- **After startup:**
  - The project must contain exactly one `db-test` container, running and `healthy`, with image `postgres:16-alpine`.
  - Its only port binding must be `127.0.0.1:5433->5432/tcp`.
  - Its only mounts must be the two read-only bind mounts (`/docker-entrypoint-initdb.d` and `/etc/careerpilot/pg_hba.conf`), with no volume of any kind, and `/var/lib/postgresql/data` must be tmpfs.
  - The check for other running containers on 5433 repeats.
- **Before pytest:** with the test `POSTGRES_*` set, a short Python/psycopg check connects to `127.0.0.1:5433`, the exact endpoint pytest uses. It must read `cluster_name = careerpilot-test` and `hba_file = /etc/careerpilot/pg_hba.conf`. The check is sent to `python -` on stdin to avoid PowerShell 5.1 quoting. On a connection failure it prints only the exception type, never a message, URL, or credential.
- **Exit codes:** pytest's own code; 2 for an invalid `-Path` or a missing tool; 3 for a refused safety check. Unknown parameters are rejected by PowerShell's own parameter binding with exit 1, which is also pytest's "tests failed" code. The help text originally said "2 for invalid usage"; the pre-commit review corrected it (documentation only).
- **Not checked:** the time between the final check and pytest connecting (a time-of-check/time-of-use gap). Also, a listener is attributed to the test container only by the container's own port binding, not by matching the owning process.

### Security Limitations

- **Fixed test superuser credentials are committed** in `docker-compose.test.yml`, `ci.yml`, and `ops/test-backend.ps1`. They are non-secret by design. Anyone on the local machine who knows them gets superuser on the throwaway test container. With that, PostgreSQL superuser features allow code execution inside that container, but not on the host. The port is bound to `127.0.0.1` only.
- **`local all all trust` inside the container.** Anyone who can `docker exec` into the test container can connect as any role without a password. Such a person already controls the container.
- **Plain `python -m pytest backend/tests` still targets the development cluster's `careerpilot_test`** (the `.env` settings, port 5432), as before. Only the helper script and CI use the isolated container. `CLAUDE.md` still documents the plain command. Updating it is planned for Stage E and was outside this stage's file list.
- **Leftovers in the development cluster.** The existing `careerpilot_test` database and `careerpilot_test_reader` role there are untouched. Removing them would be a destructive operation and needs separate approval.
- **The container keeps running** between local runs until `docker compose -p careerpilot-test -f docker-compose.test.yml down`.
- **Assumptions:** confirmed locally by Tier 2 (see below): the entrypoint behaviour, tmpfs creating no anonymous volume, the Windows bind mounts, and `up --wait` on Docker Desktop. On GitHub's `ubuntu-latest` runner, the **Start isolated test PostgreSQL** step (`up --detach --wait`) succeeded in run `39286486531`. The detailed container checks (markers, mounts, volumes) were run only locally, not in CI.
- **Latent local port conflict (found in Tier 2).** A stopped container from an unrelated project, `pipeline-kestra_postgres-1`, is configured to publish `0.0.0.0:5433`. It was exited during verification, so there was no conflict, but starting it would clash with the test container. After the safety patch, the helper warns about it while it is stopped and refuses to run if it is running. (CI does not use the helper; a GitHub runner has no such containers.)
- **The `postgres` database in the test cluster keeps default ACLs** (PUBLIC has CONNECT and TEMP). The reader is NOLOGIN. The future test LOGIN role is blocked from it by `pg_hba.conf`, which a Stage C probe test will verify with a real login attempt.

### Verification Results (Tier 1, Read-Only)

The developer approved the Tier 1 checks only. They started no container, ran no SQL or pytest, and changed no files.

| # | Check | Result |
|---|---|---|
| 1 | `docker compose -p careerpilot-test -f docker-compose.test.yml config --quiet` | Passed (exit 0) |
| 2 | PowerShell parser (`[System.Management.Automation.Language.Parser]::ParseFile`) on `ops/test-backend.ps1`, Windows PowerShell 5.1.26100 | Passed: 0 parse errors |
| 3 | `yaml.safe_load` on `.github/workflows/ci.yml` and `docker-compose.test.yml` | Passed |
| 4 | `git check-attr eol` on `pg_hba.conf`, `01_test_reader_role.sql`, `02_test_reader_grants.sql` | Passed: all `eol: lf` |
| 5a | `ops/test-backend.ps1 -Path README.md` | Refused before Docker: "-Path must be inside backend/tests" (exit 2) |
| 5b | `ops/test-backend.ps1 -Path backend/tests/nope.py` | Refused before Docker: "-Path does not exist" (exit 2) |
| 5c | `ops/test-backend.ps1 -k foo` | Refused by parameter binding: "A parameter cannot be found that matches parameter name 'k'" (exit 1) |
| 5d | Dot-sourcing the script in a child PowerShell | Refused with the dot-source error. The shell kept running, and `POSTGRES_PORT` was still unset afterwards. |

Every check in 5 ran in a child `powershell -NoProfile -ExecutionPolicy Bypass` process and stopped before Docker was called.

The first two attempts at 5d gave inconclusive output because of quoting in the test command itself, not the script. The outer shell expanded `$env:` early, and Windows PowerShell 5.1 stripped the inner quotes. It was rerun with `-EncodedCommand`, which gave the result above.

Before the checks, the new files were confirmed to be pure ASCII (Windows PowerShell 5.1 misreads non-ASCII in files without a BOM), and `git diff` was reviewed.

**Not covered by Tier 1:**
- the container's startup with the custom `pg_hba.conf`
- tmpfs avoiding an anonymous volume
- the Windows bind mounts
- `up --wait`
- the test suite against the container

### Verification Results (Tier 2, Local Container)

The developer approved starting only the `careerpilot-test` project, running the existing suite against it, and shutting it down. No files were edited during the run. All SQL run against the container was read-only catalog queries, apart from what the image's initialization and pytest themselves do inside `careerpilot_test`.

**Pre-checks (before starting anything):**
- **Development stack:** `careerpilot-db-1`, `careerpilot-backend-1`, and `careerpilot-frontend-1` were in Compose project `careerpilot`, with the database on `127.0.0.1:5432` and healthy. Their start times and restart counts (0) were recorded.
- **No test resources:** no `careerpilot-test` containers, networks, or volumes existed.
- **Port 5433:** not listening.
- **Volume baseline:** 43 volumes, including existing anonymous volumes from other projects. The full list was saved for comparison.

**Results:**

| # | Check | Result |
|---|---|---|
| 1 | `docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait` | Exit 0. It created only network `careerpilot-test_default` and container `careerpilot-test-db-test-1`, which reached healthy. |
| 2 | Health and markers | `healthy`, 0 restarts. PostgreSQL 16.14. `cluster_name = careerpilot-test`, `hba_file = /etc/careerpilot/pg_hba.conf`, `password_encryption = scram-sha-256`. |
| 2 | Initialization with the custom `pg_hba.conf` | Container log, in order: the temporary initialization server became ready (pid 42), `CREATE DATABASE`, `01_test_reader_role.sql` (`BEGIN`/`DO`/`COMMIT`), `02_test_reader_grants.sql` (`BEGIN`/`DO`/`DO`/`COMMIT`), then the real server became ready (pid 1). `pg_hba_file_rules`: 5 rules in file order, no errors, and the three `careerpilot_test_demo_login` rules come first. |
| 3 | `careerpilot_test_reader` attributes | NOLOGIN. No SUPERUSER, INHERIT, CREATEDB, CREATEROLE, REPLICATION, or BYPASSRLS. `CONNECTION LIMIT 0`, 0 memberships in either direction, 0 role settings, owns nothing. |
| 3 | `careerpilot_test_reader` privileges | CONNECT and `USAGE` on `public`. No TEMPORARY or CREATE on the database, no CREATE on `public`, no `pg_read_all_data`/`pg_write_all_data`. One default ACL: `SELECT` (no grant option) on tables created by `careerpilot_test_admin` in `public`. Its only `pg_shdepend` references are in `careerpilot_test` (one `pg_namespace` ACL, one `pg_default_acl` ACL); there are none on shared objects or in other databases. PUBLIC's TEMPORARY on `careerpilot_test` is revoked (`=c/`). |
| 4 | Databases in the cluster | Only `careerpilot_test`, `postgres`, `template0`, `template1`, all owned by the test superuser. No development database. |
| 4 | Mounts | Two read-only bind mounts (`pg_hba.conf` and `backend/tests/sql`) and a tmpfs data directory (`/proc/mounts`: `tmpfs ... rw,nosuid,nodev,noexec`). No named volume. |
| 4 | Anonymous volume | **None created.** 43 volumes before and after, same names. |
| 4 | Network and port | Only `careerpilot-test_default`, with this container as its only member. The port is bound to `127.0.0.1:5433` only. |
| 5 | `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1` | **314 passed, 0 failed**, 1 warning (the existing `httpx`/starlette deprecation warning), 9.60 s, helper exit 0. |
| 5 | The run used the isolated cluster | Afterwards the container's `careerpilot_test` showed 1,176 committed transactions, and `job_applications` (owned by `careerpilot_test_admin`) carried `careerpilot_test_reader=r` from the default privilege. |
| 6 | Output scan for secrets | The test admin password: 0 occurrences. `5432`: 0. The 9 lines matching `postgresql://` or `PASSWORD` are names of existing parametrized tests that use deliberate placeholder values (`demo-placeholder-secret`, `owner-secret-value`) on the never-resolving `.invalid` domain, or the variable name `POSTGRES_PASSWORD`. |
| 7 | `docker compose -p careerpilot-test -f docker-compose.test.yml down` (no `-v`) | Exit 0. It removed only the test container and the test network. |
| 7 | After shutdown | Dev containers have the same start times, 0 restarts, and are still up (the database healthy). No `careerpilot-test` containers or networks remain. Volumes are unchanged (43). Port 5433 is free. |

**Security findings:** none. An improvement over running tests in the development cluster: the owner-privilege test lists the databases its user owns, and it now sees only the test cluster, so the development database's name can no longer appear in test output (see Entry 009's Human Oversight note). The two non-blocking observations (the latent 5433 conflict and default ACLs on `postgres`) are listed under Security Limitations.

**Process notes:**
- One `docker ps --format` call failed because Windows PowerShell 5.1 strips the inner quotes in a Go template. It was rerun from Bash.
- The first volume comparison falsely reported every line as different because the PowerShell-written baseline used CRLF line endings. It was rerun with `diff --strip-trailing-cr`.
- Temporary comparison files in `%TEMP%` were deleted afterwards.

**Scope of these results:** Tier 1 and Tier 2 above ran against the helper **before** the safety patch.

### Verification Results (Safety Patch, Tier 1, Read-Only)

The developer approved the Tier 1 checks only. They started no container, ran no Docker command, SQL, or pytest, and changed no files.

| # | Check | Result |
|---|---|---|
| 1 | PowerShell parser (`[System.Management.Automation.Language.Parser]::ParseFile`) on the patched `ops/test-backend.ps1`, Windows PowerShell 5.1 | Passed: 0 parse errors |
| 2 | `ops/test-backend.ps1 -Path README.md` | Refused: "-Path must be inside backend/tests: README.md" (exit 2) |
| 3 | `ops/test-backend.ps1 -Path backend/tests/nope.py` | Refused: "-Path does not exist: backend/tests/nope.py" (exit 2) |
| 4 | `ops/test-backend.ps1 -k foo` | Refused by parameter binding: "A parameter cannot be found that matches parameter name 'k'" (exit 1) |
| 5 | Dot-sourcing the script in a child PowerShell (sent with `-EncodedCommand`) | Refused with the dot-source error. The shell kept running, and `POSTGRES_PORT` was still unset afterwards. |

Every check ran in a child `powershell -NoProfile -ExecutionPolicy Bypass` process. Each refusal happened during argument validation, before any of the new Docker checks. Before the checks, the patched file was confirmed to be pure ASCII, and its diff against the reviewed version was shown to the developer.

**Not covered by this Tier 1:** every new safety check, because each one needs Docker (project contents, other containers and listeners on port 5433, the container check after startup, and the `127.0.0.1:5433` check of `cluster_name` and `hba_file`).

### Verification Results (Safety Patch, Tier 2, Local Container)

The developer approved starting and stopping only the `careerpilot-test` project, running the existing tests through the patched helper, and opening a temporary local TCP listener only to test the port refusal. No files were edited during the run.

**Baseline:**
- `careerpilot-db-1`, `careerpilot-backend-1`, and `careerpilot-frontend-1` were running with 0 restarts. Their start times were recorded.
- `careerpilot-test` had 0 containers, networks, and volumes. There were 43 volumes in total, and port 5433 was not listening.

**Results:**

| # | Command | Result |
|---|---|---|
| 1 | `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1` | Printed the expected warning: "stopped container pipeline-kestra_postgres-1 is configured to publish host port 5433; starting it would conflict." The checks before startup passed, then `up --detach --wait` created the network and container and reached `Healthy`. The checks after startup and the `127.0.0.1:5433` marker check passed; they print nothing on success, and pytest runs only after all of them, with 0 refusal lines in the output. **314 passed, 0 failed**, 1 warning (the existing `httpx`/starlette deprecation warning), 9.91 s, **exit 0**. Checked independently afterwards: the container was `running`/`healthy` with image `postgres:16-alpine`, and its markers read `careerpilot-test`, `/etc/careerpilot/pg_hba.conf`. |
| 2 | `... test-backend.ps1 -Path backend/tests/test_health.py`, with the container still running | 1 item collected, **1 passed**, **exit 0**. Only the selected file ran. The container's start time was unchanged, so it was reused, and the listener on 5433 was correctly accepted as the test container's own. |
| 3 | `docker compose -p careerpilot-test -f docker-compose.test.yml down` (no `-v`) | Exit 0. It removed only the test container and the test network. Port 5433 was free afterwards. |
| 4 | Temporary .NET `TcpListener` on `127.0.0.1:5433` in the calling PowerShell (PID 24604); the helper run as a child process; `$listener.Stop()` in `finally` | Refused before Docker Compose startup: "refusing to run the tests: port 5433 is already in use by powershell (PID 24604), not by the careerpilot-test container." **Exit 3**, naming the listener's own process. Compose did not run: there was no `Creating` output, and no `careerpilot-test` container or network existed afterwards. The listener was stopped and port 5433 was free again. |
| 5 | Final state | `careerpilot-test`: 0 containers, networks, and volumes. All 43 volumes unchanged. The development containers had the same start times, 0 restarts, and were still running. `pipeline-kestra_postgres-1` was still `exited` and was never touched. The test admin password appeared 0 times in the helper output. Temporary output files were deleted. |

**Problems:** none in the helper.

**Process notes:**
- In step 1, the calling command's own `*>&1` capture turned docker's progress output into `NativeCommandError` text. This came from the outer capture, not the helper; it is the Windows PowerShell 5.1 behaviour the helper avoids by not using `Stop`.
- The safety checks print nothing on success, so in normal use the only sign they ran is that pytest starts. A one-line success message was suggested but not added.

### Commit and Push

- **Pre-commit review:** `git status` showed exactly the six intended files. `git diff --check` was clean. The untracked files had no trailing whitespace, tabs, or non-ASCII characters. The only credential was the documented test value, plus the docker-build job's existing dummy `ci` value, which is outside this diff. There were no SQL, role, or grant changes. The log change was append-only.
  - One finding was fixed before committing (documentation only): the helper's help text said "2 for invalid usage", but unknown parameters exit 1 from PowerShell's parameter binding. The helper re-parsed with 0 errors after the fix.
- **Commit:** `64f42b0` "Add isolated PostgreSQL test container for backend tests and CI" contains exactly the six files (712 insertions, 43 deletions). `git ls-files --eol` confirmed `pg_hba.conf`, `01`, and `02` are stored and checked out with LF.
- **Push (developer-approved):** before pushing, these were confirmed:
  - The branch was `feature/render-readonly-demo`, HEAD was `64f42b0`, and the tree was clean.
  - The branch was 1 ahead and 0 behind its origin branch.
  - PR #2 was open and unmerged, with base `main` and head `robanc/CareerPilot:feature/render-readonly-demo` at `feb86c1`. `gh` is not installed, so this was read through the unauthenticated GitHub REST API (public repository).

  Then `git push origin feature/render-readonly-demo` fast-forwarded `feb86c1..64f42b0`. There was no force push, no new PR, and no merge.

### GitHub Actions (PR #2)

**Run:** https://github.com/robanc/CareerPilot/actions/runs/39286486531. Event `pull_request`, head `64f42b0`, associated with PR #2. Run status: **`completed` / `success`**.

| Job | Result |
|---|---|
| Frontend lint and build | `success` (16:34:14Z–16:34:23Z) |
| Docker image build verification | `success` (16:34:14Z–16:34:44Z) |
| Backend tests (pytest + PostgreSQL 16) | **`success`, 26 s** (confirmed visually by the developer in the GitHub Actions UI). Steps per the API: Set up job, checkout, Python 3.12, and install `success`; **Start isolated test PostgreSQL `success` (9 s)**; **Run pytest `success` (5 s)**; Show test PostgreSQL logs `skipped` (it runs only on failure); post-steps and Complete job `success`. |

The developer also visually confirmed that the frontend and Docker build jobs succeeded in this run.

**Resolved: the earlier `in_progress` uncertainty.** Right after the run finished, and again on a re-check, Claude Code's unauthenticated API requests returned the `backend-tests` job record and its check run as `in_progress`, with no conclusion and no completion time. That was despite the run-level `success` and every step having completed successfully. The developer then confirmed in the GitHub Actions UI that the job succeeded in 26 seconds. The API record was a lagging state, not a failure or a hung job.

**pytest count: not separately verified.** The job log, which needs authentication and could not be read because `gh` is not installed, was not checked for the count. The `Run pytest` step succeeded, meaning pytest exited 0, but the number of tests that ran in CI (314 locally) is not recorded here as confirmed.

**Second run: documentation commit `0ace3a3`.** The CI record above was committed as `0ace3a3` ("Document Stage A GitHub Actions verification", log only) and pushed to PR #2 as a normal fast-forward, `64f42b0..0ace3a3`. That push started run https://github.com/robanc/CareerPilot/actions/runs/39289469411 (event `pull_request`). Claude Code monitored it through unauthenticated, read-only API requests every 40 seconds until it finished. Run status: **`completed` / `success`**.

| Job | Job record | Steps |
|---|---|---|
| Backend tests (pytest + PostgreSQL 16) | `completed` / `success` | 10, all `success` or `skipped` |
| Docker image build verification | `completed` / `success` | 7, all `success` or `skipped` |
| Frontend lint and build | `completed` / `success` | 9, all `success` or `skipped` |

In this run, the `backend-tests` job record itself reported `completed` / `success` through the API, unlike run `39286486531`, where it lagged at `in_progress`. The commit changed only this log, so the run tested the same code as `64f42b0`. It is a second, independent CI pass of the isolated test container setup. The pytest count was again not read, because job logs require authentication.

### Verification Pending

- (Optional) The exact pytest count in either CI run's `backend-tests` log: https://github.com/robanc/CareerPilot/actions/runs/39286486531/job/118174239766 or https://github.com/robanc/CareerPilot/actions/runs/39289469411/job/118186035593. Both jobs' success is confirmed.

### Human Oversight

Claude Code created or edited only the five listed files and this log. With the developer's approval, it ran the Tier 1 read-only checks and then the Tier 2 verification. Tier 2 started and stopped only the `careerpilot-test` Compose project, ran read-only catalog queries in the test container, and ran the existing test suite through `ops/test-backend.ps1`. It did not stop, restart, or modify any development container, create scripts 03–05 or the LOGIN role, change permissions outside the test container, use `down -v`, read `.env` or any secret, commit, push, merge, or deploy.

For the safety patch, Claude Code edited only `ops/test-backend.ps1` and this entry. With the developer's approval, it then ran the patch's Tier 1 read-only checks and its Tier 2 verification above. Tier 2 started and stopped only the `careerpilot-test` project, ran the existing tests through the helper, and opened (then closed) one temporary listener on `127.0.0.1:5433`. It did not touch any development or unrelated container, use `down -v`, change SQL or roles, read `.env` or any secret, commit, push, merge, or deploy.

After the developer approved, Claude Code:
- committed `64f42b0`
- pushed it to the existing PR #2 branch, without a force push
- monitored GitHub Actions through read-only, unauthenticated API requests

It did not merge, deploy, open a new PR, or start Stage B. This CI section was then added to the log. The `backend-tests` success was confirmed by the developer, who checked it visually in the GitHub Actions UI. Claude Code did not have authenticated access to the job.

With further approval, Claude Code committed that CI section as `0ace3a3` (log only), pushed it normally, without a force push, and monitored the resulting run `39289469411` until it finished. The second-run note was then added to this entry, and is not yet committed.

### Remaining Deployment Blockers

- Step 73D-2 Stages B–E: scripts 03–05, the ephemeral SCRAM password fixture with its safety gate, real-login and negative privilege tests, and documentation.
- The later Step 73D phases: Render provisioning scripts and runbook, admin bootstrap and fictional seed, and deployment.
- Rate limiting, resume input limits, and synthetic-data safeguards.

`public_demo` remains **NOT SAFE TO DEPLOY**.

### Outcome

The files for an isolated, disposable PostgreSQL 16 test cluster are in place, for both local Windows runs and CI. Locally, the container initializes correctly with the custom `pg_hba.conf`, provisions `careerpilot_test_reader` exactly as in CI before, stays isolated from the development stack, and passes the full existing suite (314 passed). The helper's later safety patch has been verified locally: it passes the full suite, reuses a running test container, and refuses a foreign listener on port 5433 before starting anything. In CI (PR #2, run `39286486531`), all three jobs succeeded. `backend-tests` (26 s) started the isolated container on `ubuntu-latest` and ran pytest successfully. A second run (`39289469411`, for the documentation commit `0ace3a3`) also succeeded, with all three job records `completed` / `success`. The exact CI test count was not separately verified.


## Entry 011 — MVP Completion: Frontend, Public-Demo Safety, Render Preparation, and Release Validation

**Date:** October 20, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented on branch `feature/render-readonly-demo`, not committed. Backend suite: 412 passed, 0 failed, run once through `ops/test-backend.ps1` with the developer's approval. Frontend: lint clean, 21 of 21 Vitest tests passed, build succeeded. Nothing deployed; `public_demo` remains **NOT SAFE TO DEPLOY** until the Render procedure is complete.

### Objective

Complete the MVP for the October 23 deadline, in the order the developer set:

- **Stage B preparation:** prepare the test-cluster LOGIN role drafts. They were reviewed and staged but not executed, and were later deprioritized.
- **Test-runner hardening.**
- **Task 1:** frontend completion.
- **Task 2:** public-demo safety minimums.
- **Task 3:** Render deployment preparation.
- **Release validation.**

### Tasks and Prompts (summarized)

- **Stage B:**
  - Stage the three revised `.sql.review` drafts for execution.
  - Resolve the 04 → 05 include.
  - Write a controlled execution plan.
  - Then revise that plan: the scope of the large-object REVOKE, table-presence strategy, pytest targeting, HBA and real-session checks.
- **Runner:**
  - Recognize the split Stage A mounts.
  - Add a config-hash recreation safeguard.
  - Finally: require the existing running, healthy container and never create, start, or recreate one; neutralize `.env` and the application and libpq variables.
- **Task 1:** a central API module; complete create and edit forms; interview notes; dashboard-to-record navigation; the heuristic label; Vitest.
- **Task 2:**
  - resume input limits;
  - rate limiting with HTTP 429;
  - a guarded, idempotent fictional seed;
  - frontend public-demo awareness;
  - `npm test` in CI.
- **Task 3:**
  - research Render's role capabilities;
  - `render.yaml`;
  - an approval-gated deploy workflow;
  - Render provisioning SQL drafts;
  - stricter seed target checks;
  - the deployment guide.
- **Validation:** a consolidated review; a deployed-commit verification gate; a conftest endpoint guard; one approved backend test run.

### Context Supplied

`product-spec.md`, `openapi.yaml`, `AGENTS.md`, `CLAUDE.md`, the existing backend and frontend code and tests, `docker-compose.test.yml`, the CI workflow, and Render's public documentation (Blueprint spec, database credentials, deploy hooks, rewrites, environment variables).

### Files Changed

- **Backend application:**
  - `backend/app/limits.py` (new): rate limiting and a 256 KiB body cap. Both apply in `public_demo` only; `/health` is exempt.
  - `main.py`: middleware order; `GET /config`; `GET /version`, which reports `RENDER_GIT_COMMIT` only when it is a full SHA.
  - `schemas.py`: 20,000-character resume and job description limits; `ConfigResponse`, `VersionResponse`.
  - `readonly.py`: a reusable JSON error helper.
  - `settings.py`: an updated warning.
- **Seed:** `backend/scripts/seed_demo_data.py` (new), an idempotent fictional seed. It requires:
  - the target in `CAREERPILOT_SEED_DATABASE_URL` only;
  - an allowlisted database;
  - matching `--expect-database`, `--expect-host` and `--expect-user`;
  - TLS, a non-superuser, and PostgreSQL 16;
  - only seed rows already in the table;
  - for writes, `--apply` plus an exact `--confirm`.
- **Frontend:**
  - `src/api.js` (new);
  - `Applications.jsx`: full create and edit forms, interview notes, the dashboard focus, read-only mode;
  - `App.jsx`: navigation, `/config`, the demo banner;
  - `ResumeMatch.jsx`: the heuristic label, input limits, 429/413 messages;
  - `App.css`;
  - `scripts/write-version.mjs` (new);
  - Vitest setup in `vite.config.js` and `package.json`/`package-lock.json`.
- **Tests:**
  - Backend:
    - new: `test_request_limits.py`, `test_seed_demo_data.py`, `test_render_provisioning_sql.py`, `test_version.py`;
    - `conftest.py`: a rate-limiter reset, and a guard that refuses any endpoint other than 127.0.0.1:5433.
  - Frontend: `api.test.js`, `App.test.jsx`, `Applications.test.jsx`, `ResumeMatch.test.jsx`, `src/test/mockFetch.js`.
- **CI/CD and ops:**
  - `ci.yml`: an `npm test` step and `workflow_call`.
  - `deploy.yml` (new): guard → reusable CI → `production` environment approval → deploy hooks at the same commit → smoke.
  - `ops/smoke-test-render.sh` (new): a deployed-commit gate before any check; non-mutating write probes; an abort unless read-only is confirmed.
  - `ops/test-backend.ps1`: existing container only, read-only Docker calls, environment neutralization, a re-check before pytest.
  - `docker-compose.test.yml`: mounts only Stage A scripts 01 and 02.
- **Deployment:**
  - `render.yaml` (new): auto-deploy off; database closed to external connections; reader URL entered by hand; `FORWARDED_ALLOW_IPS` pinned; `version.json` with no-store caching.
  - `deploy/render/01–03_*.sql.review` (new): schema, SELECT-only role, and verifier drafts.
  - `docs/deployment-render.md` (new).
- **Documentation:**
  - `README.md`: features, architecture, setup, testing, CI/CD, security, AI-assisted development.
  - `CLAUDE.md`: test commands, endpoints, deploy workflow.
  - `docs/agent-extension-pack.md` (new).
  - `.gitattributes`: LF for `ops/*.sh`.
  - `openapi.yaml`: `/config`, `/version`, `maxLength`, 413/429.
  - This entry.

### Manual Review and Corrections

- **The smoke test could have written data.** Its write probes would have created, changed, and deleted records on a wrongly writable API, and it did not stop on a failed mode check. It now aborts unless the API reports read-only mode, and every probe is harmless even if accepted (an empty body; id 0).
- **The smoke job could not read its URLs.** They were documented as `production` environment variables, which the smoke job cannot see; they are now repository variables. The guide also requires the hook secrets to be environment-only, and the environment to exist before the first run.
- **The smoke test could pass on an old release.** The deployed-commit gate now requires `/version`, `/api/version`, and `/version.json` to report `EXPECTED_COMMIT` before any other check, and fails otherwise.
- **Render's runtime variables:** Render's Python runtime sets `FORWARDED_ALLOW_IPS=*`. With that, uvicorn trusts the leftmost `X-Forwarded-For` entry, which the client chooses; this was confirmed in the uvicorn 0.54 source. The value is now pinned to uvicorn's default.
- **Render role capability is undocumented.** The SQL drafts and the guide make it a read-only verification step that fails closed.
- **Agent-side mistakes, all caught and corrected:**
  - a shell heredoc failed to parse, and nothing was written;
  - a fetch-mock bug and a test-harness bug;
  - an escaped `\t` that corrupted a `CLAUDE.md` command;
  - a relative-path error in one validation command, which then ran nothing.
- **Incident:** the developer approved a mock-server validation command containing `rm -f` on a temporary log file, under `%LOCALAPPDATA%\Temp\stageb-tools`, outside the repository. Read-only verification showed that only that log file was affected. All project files, the Stage B hashes, the containers, and the databases were unchanged. Later validation commands avoided deletion entirely.

### Tests Executed

- **Backend (approved, once):**
  - **Command:** `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1`.
  - **Result:** **412 passed, 0 failed** (13.6 s). New files: `test_request_limits` 38, `test_seed_demo_data` 42, `test_render_provisioning_sql` 10, `test_version` 8.
  - **Runner output:** one warning that a stopped container from another project is configured for port 5433.
  - **Afterwards:** the test container kept the same ID and start time.
- **Frontend:** `npm run lint` clean; `npm test` 21 of 21 passed; `npm run build` succeeded.
- **Static and mocked checks, all passing:**
  - Python compile; YAML parsing; `bash -n`; `node --check`.
  - PowerShell AST parse with 0 errors, plus harnesses: 20 container-match cases, 9 existing-container cases, environment save and restore with dummy values.
  - The conftest guard in subprocesses with `.env` disabled and psycopg's connect blocked (5 cases).
  - `/version` locally without a database (9 cases).
  - The smoke gate against a 127.0.0.1 mock (6 scenarios), with 0 write probes sent to a writable API.
  - The seed target checks offline.

### Human Oversight

- **What the developer approved and Claude Code ran:** the single backend test run, and read-only Docker inspection.
- **What did not happen:** no Stage B SQL, Render SQL, seeding, Docker container changes, commits, pushes, merges, or deployment. No `.env` file or secret was read.

### Remaining Release Blockers

- **The agent extension pack** (spec Definition of Done) is not implemented; see `docs/agent-extension-pack.md`.
- **API module location:** `AGENTS.md` places it at `frontend/src/services/api.js`, but it was created as `frontend/src/api.js`. It needs a move, or a decision to amend `AGENTS.md`.
- **Render:** the capability check (CREATEROLE, non-superuser, TLS at PostgreSQL), provisioning, seeding, the first release, and the smoke run.
- **CI:** the new tests and the frontend test step have not yet run in GitHub Actions.

### Outcome

The application features in the MVP specification are implemented and tested locally: the backend passes 412 tests and the frontend 21. Public-demo protections are in place: write blocking, a SELECT-only startup check, rate and size limits, and fictional data only. Deployment is prepared but not performed. The agent extension pack remains the main incomplete item in the Definition of Done.

## Entry 012 — Agent Extension Pack and API Module Location

**Date:** October 20, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented on branch `feature/render-readonly-demo`, not committed. Extension tests: 53 passed. Frontend: lint clean, 21 of 21 tests passed. Backend tests were not rerun: no backend code changed.

### Objective

Close the two blockers left by Entry 011:
- `frontend/src/api.js` moves to `frontend/src/services/api.js`, as `AGENTS.md` requires.
- The extension pack the spec requires is implemented, with no placeholders: a skill, a subagent, a guardrail hook, an MCP server, a custom agent, and a permissions document.

### Files Changed

- **API module move:** `frontend/src/services/api.js` and `services/api.test.js` (moved). Imports updated in `App.jsx`, `Applications.jsx`, `ResumeMatch.jsx`, and `test/mockFetch.js`. Behavior is unchanged.
- **Skill and subagent:** `.agents/skills/careerpilot-safe-test-run/SKILL.md`, `.agents/agents/security-reviewer.md`, `.agents/tests/test_agent_definitions.py`.
- **Guardrail:** `agent-hooks/guard.py`, `agent-hooks/tests/test_guard.py`, `.claude/settings.json` (PreToolUse hook with `onFailure: block`, plus `.env` deny rules).
- **MCP server:** `mcp-server/careerpilot_mcp.py`, `mcp-server/tests/test_careerpilot_mcp.py`, `.mcp.json`.
- **Custom agent:** `custom-agent/release_auditor.py`, `custom-agent/tests/test_release_auditor.py`.
- **CI:** `.github/workflows/ci.yml` gains an `agent-extensions` job (stdlib `unittest`, Python 3.12).
- **Documentation:** `docs/permissions.md` (new); `docs/agent-extension-pack.md` (rewritten); `README.md` (module path, extension tests, CI table, deployment paragraph deduplicated); this entry.

### Manual Review and Corrections

- **Unexpected activation:** the hook took effect mid-session as soon as `.claude/settings.json` was written. The agent had expected it to wait for a restart.
- **Fail closed while half-edited:** an Edit removed a helper that a second Edit was meant to replace. The live guard then hit a `NameError` and denied every file-tool call, reporting it as a parse failure. The agent repaired `guard.py` through a Bash command, which the guard did not then treat as a file write. That was a bypass of the intended approval, and it is now closed:
  - shell writes to protected files get `ask`;
  - internal errors are denied with an accurate reason.

  The developer approved the full rewrite when the guard asked.
- **Further defects found by tests and pipe tests, all fixed:**
  - a `TRUNCATE` pattern that could never match;
  - an `lstrip` path bug;
  - project-root matching that failed for Git-Bash-style paths (protected files are now matched by suffix).
- **Guard working as intended:** it denied the agent's own test command that named a `.env` file.
- **Developer interventions:**
  - rejected one shell-based README edit; the README was then edited with the normal file tools;
  - asked to review `.claude/settings.json`, which was left unchanged;
  - instructed that `guard.py` stay unchanged from then on.

### Tests Executed

- `python -m unittest discover -s agent-hooks/tests`: 30 passed.
- `python -m unittest discover -s mcp-server/tests`: 11 passed.
- `python -m unittest discover -s custom-agent/tests`: 6 passed.
- `python -m unittest discover -s .agents/tests`: 6 passed.
- `python custom-agent/release_auditor.py`: all six checks passed.
- Frontend `npm run lint` clean; `npm test` 21 of 21 passed.
- Real-payload check of the live guard: 6 of 6 decisions as expected.

### Human Oversight

- **Approved by the developer:** the rewrite of `guard.py`, through the guard's own ask prompt.
- **What did not happen:** no backend tests, SQL, Docker, database, Render, commit, push, merge, or deployment actions. No `.env` file or secret was read.

### Remaining Blockers

- The extension tests and the new CI job have not run in GitHub Actions yet.
- Render: the capability check, provisioning, seeding, first release, and smoke run (see `docs/deployment-render.md`).
- None in the frontend: the production build also succeeded after the module move.

## Entry 013 — Observability, Alerting, and Incident Response

**Date:** October 25, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Committed on `main` as `b8381f8` (alert rules and CI validation) and `cab1f49` (incident response runbook). The three `promtool` checks passed locally. The developer reports that GitHub Actions CI runs #22–#24 succeeded, with all five jobs passing in #23 and #24. Render deployment remains **on hold**.

### Objective

- Record the local OpenTelemetry observability stack already in the repository.
- Add local Prometheus alerting for backend 5xx rate, average latency, missing backend telemetry, and OpenTelemetry Collector availability.
- Validate the rules with synthetic `promtool` tests, locally and in CI.
- Document incident response for the four alerts.

### Context: Existing Observability Stack

The stack predates the alerting work. This summary comes from the Git history and the current files. The prompts used for these earlier commits are not part of this entry's session.

- **Commits:**
  - `c095232`: structured HTTP request logging and correlation IDs;
  - `d60b715`: Prometheus HTTP request metrics;
  - `92fee91`: protected `/metrics` endpoint;
  - `56788a3`: OpenTelemetry stack and documentation;
  - `3ea8ed6`: CI dependency fix for the agent-extensions job;
  - `42b3838`: README update.
- **Backend (`backend/app/observability.py`):**
  - OTLP export of metrics, traces, and logs to `127.0.0.1:4318`, with service name `careerpilot-backend`;
  - opt-in through `CAREERPILOT_OTLP_ENABLED=true`;
  - request logs record method, status code, duration, request ID, and trace ID, but no request bodies or resume text.
- **Monitoring stack (`monitoring/docker-compose.yml`):** a separate Compose project, `careerpilot-monitoring`, running Prometheus, the OpenTelemetry Collector, Tempo, Loki, and Grafana, with all ports bound to `127.0.0.1`.
- **Prometheus metrics:** Prometheus scrapes only the Collector (`otel-collector:8889`). The OTLP metrics appear as:
  - `careerpilot_http_requests_total`;
  - `careerpilot_http_request_duration_seconds_{bucket,sum,count}`.

  Their labels are `method`, `status_code`, and `exported_job="careerpilot-backend"`. There is no route label.
- **Existing tests:** `backend/tests/test_observability.py` contains 10 tests. `monitoring/README.md` records that all 10 passed locally. They were not rerun in this session.

### Tasks and Prompts (summarized)

1. **Read-only analysis** of the monitoring configuration and metrics, ending in a proposal. The agent confirmed metric names and labels from the files and proposed rules, tests, configuration, CI, and documentation. It also flagged that the OTLP histogram has no explicit buckets, so percentile latency is unreliable. The work then stopped for approval.
2. **Approved implementation**, with the developer's specification:
   - the four alerts, with their exact thresholds;
   - tests kept outside the rule glob;
   - no histogram fix, p95 alert, Alertmanager, notifications, or smoke scripts.
3. **Approved validation:** only the three proposed `promtool` commands.
4. **Read-only runbook planning**, then creation of exactly one file, `monitoring/INCIDENT_RESPONSE.md`.
5. **A targeted runbook revision** for accuracy (see Manual Review and Corrections).
6. **This log entry.**

### Context Supplied

- `product-spec.md`, `openapi.yaml`, `AGENTS.md`, and `CLAUDE.md`.
- `monitoring/prometheus.yml`, `docker-compose.yml`, `otel-collector.yml`, and `README.md`.
- `backend/app/observability.py`, `backend/app/main.py`, and `backend/tests/test_observability.py`.
- `.github/workflows/ci.yml` and `backend/requirements.txt`.

### Files Changed

- **Alerting (`b8381f8`):**
  - `monitoring/alerts/careerpilot.rules.yml` (new). It holds four rules:
    - `CareerPilotHigh5xxRate`: 5xx ratio above 5%, with at least 10 requests in 5 minutes, for 5 minutes (warning);
    - `CareerPilotHighAverageLatency`: average latency above 0.5 seconds, for 10 minutes (warning);
    - `CareerPilotBackendTelemetryMissing`: `absent()` of the backend request series, for 5 minutes (info);
    - `CareerPilotOtelCollectorDown`: `up == 0` on the Collector, for 2 minutes (warning).
  - `monitoring/alerts/tests/careerpilot.rules.test.yml` (new): 9 synthetic test cases with 15 alert checks.
  - `monitoring/prometheus.yml`: added `evaluation_interval: 15s` and `rule_files: /etc/prometheus/alerts/*.rules.yml`.
  - `monitoring/docker-compose.yml`: added a read-only `./alerts` mount for Prometheus.
  - `.github/workflows/ci.yml`: added a `monitoring-config` job that runs `promtool check config`, `check rules`, and `test rules` from `prom/prometheus:v3.14.0`.
  - `monitoring/README.md`: new "Alerting" section and one privacy line.
- **Runbook (`cab1f49`):** `monitoring/INCIDENT_RESPONSE.md` (new). It covers:
  - scope and safety rules;
  - severities, triage, and the four alert playbooks;
  - expected versus unexpected missing telemetry;
  - investigation in Prometheus, Grafana, Loki, and Tempo;
  - conditional recovery verification and escalation;
  - an incident report template and known limitations.
- **Documentation:** this entry.

### Manual Review and Corrections

- **Agent self-corrections:**
  - A plain `restart` does not add a new volume mount. The README now says to recreate Prometheus once with `up -d --pull never prometheus`.
  - The first static-check run failed only because Windows returned a `\` path separator. The comparison was normalized and the check rerun.
  - The editor flagged unchanged lines in `ci.yml`. PyYAML parsed the workflow with all five jobs, so the agent judged the diagnostics stale.
  - The agent added `--pull never` to the three approved `promtool` commands, so a missing image could not be downloaded. The image was already present locally.
  - In the runbook revision, the agent toned down a claim about SDK export retries that it had not verified.
- **Developer-requested runbook corrections:**
  - PromQL examples became single, directly pasteable queries, with explanations moved outside the code blocks.
  - Recovery verification now depends on the incident type and whether OTLP is enabled. Read-only checks are separated from synthetic requests, which require approval.
  - Collector-outage wording is qualified: telemetry may be delayed or lost depending on outage duration, and `CareerPilotBackendTelemetryMissing` may fire only after its own delay.

  Alongside these, the template's verification checklist was aligned with the conditional verification.
- **Unverified assumptions, marked in the runbook:**
  - the LogQL `| json` queries;
  - whether a backend running in Docker can reach `127.0.0.1:4318`;
  - all alert firing and clear-down timings, which are derived from the rules, not measured.
- **Open documentation items, not changed:**
  - `README.md` still says automated alerting is "not yet established";
  - `AGENTS.md` places runbooks under `ops/`, but the runbook is in `monitoring/`.

### Tests Executed

**Local (run by the agent):**

- **Static consistency check** (inline `python -I` with PyYAML). Passed after the path fix:
  - all six affected YAML files parse;
  - the rule glob matches only the rules file;
  - the four alert names and `for` durations are as specified;
  - the metric names match `observability.py`;
  - the expected test annotations and severities match the rules.
- **`git diff --check`:** clean.
- **`promtool`**, run in short-lived `prom/prometheus:v3.14.0` containers with `--pull never`:
  - `check config /etc/prometheus/prometheus.yml`: SUCCESS, 1 rule file and 4 rules found;
  - `check rules /etc/prometheus/alerts/careerpilot.rules.yml`: SUCCESS, 4 rules found;
  - `test rules /etc/prometheus/alerts/tests/careerpilot.rules.test.yml`: SUCCESS.
- **Not run in this session:** backend pytest, frontend lint, tests, and build. No application code changed.

**GitHub Actions (reported by the developer):**

- CI runs #22, #23, and #24 succeeded.
- All five jobs passed in #23 and #24: `backend-tests`, `frontend`, `agent-extensions`, `monitoring-config`, and `docker-build`.
- The agent could not verify these runs independently, because the `gh` CLI is not installed locally.

### Human Oversight

- **Approved by the developer:**
  - the implementation scope;
  - the three `promtool` commands;
  - the runbook outline and its single-file creation;
  - the runbook corrections.
- **Committed by the developer:** `b8381f8` and `cab1f49`. The agent did not stage, commit, or push.
- **What did not happen:**
  - no access to or changes in the development PostgreSQL database, the test database, or the protected backups (`careerpilot_backup.dump`, `backend/tests/sql/stage-b-original-backup/`, `backend/tests/stage-b-staging/`);
  - no changes to running Docker services or volumes;
  - no deployment, and no Render changes;
  - no `.env` file or secret was read.

### Remaining Items

- **Render deployment** remains on hold. The monitoring stack and alerts are local-only and do not cover Render.
- **No notifications:** no Alertmanager or notification integration is configured, so alerts must be checked manually.
- **Not yet implemented:**
  - the OTLP histogram bucket fix and p95 latency alert;
  - live verification of the alert labels against a running Prometheus;
  - the LogQL queries in the runbook.
- **Documentation follow-ups:** the stale alerting statement in `README.md`, and the location of the runbook relative to `ops/`.

### Outcome

CareerPilot now has local Prometheus alerting on its OpenTelemetry metrics: four rules, validated by `promtool` locally and, as reported by the developer, by the `monitoring-config` CI job. A local incident response runbook covers all four alerts and separates expected missing telemetry from real incidents. Monitoring remains local-only, and the Render deployment remains on hold.

## Entry 014 — Read-Only On-Call Investigator

**Date:** October 25, 2026
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Committed on `main` as `ae8a0ab` and pushed by the developer. Developer-verified results:
- local tests: 32 of 32 investigator tests and 38 of 38 custom-agent tests passed;
- GitHub Actions CI run #27 passed all five jobs.

The README On-Call Agent update that followed is not yet committed. Render deployment remains **on hold**.

### Objective

Add a first, minimal on-call investigation agent. It is deterministic and read-only, it turns synthetic alert evidence into a structured incident report that follows `monitoring/INCIDENT_RESPONSE.md`, and it has no live connections and takes no remediation actions.

### Tasks and Prompts (summarized)

1. **Implementation request.** The developer asked for a deterministic, read-only incident investigator that reads synthetic alert evidence from a local JSON file. The requirements:
   - recognize exactly the four Prometheus alerts and their severities;
   - validate the input strictly and never execute anything from it;
   - prioritize Collector-down alerts;
   - treat missing telemetry as needing investigation unless explicit evidence shows it is expected;
   - report root cause as unknown unless established;
   - never claim resolution without verification evidence;
   - keep secrets and raw content out of reports;
   - use the standard library only, with isolated synthetic tests.

   Scope was exactly two new files. Tests were not to be run at that step.
2. **README update.** Document the investigator in the README's On-Call Agent section, using the developer's verified results.
3. **This log entry.**

### Context Supplied

- `AGENTS.md` and `monitoring/INCIDENT_RESPONSE.md`.
- `monitoring/alerts/careerpilot.rules.yml`.
- `custom-agent/release_auditor.py` and `custom-agent/tests/test_release_auditor.py`, for conventions.
- For the README and this entry: the committed `custom-agent/oncall_investigator.py`, the README On-Call Agent section, and this log.

### Files Changed

- **`custom-agent/oncall_investigator.py`** (new, 464 lines; `ae8a0ab`). A standard-library-only CLI that takes one evidence file and optional `--json` and `--output` arguments.
  - **Input:** a strict schema (`schema_version: 1`, `"synthetic": true` required). Unknown alert names, invalid states, malformed or non-UTC-convertible timestamps, unknown fields, and over-long, multi-line, or secret-like text are rejected. Error messages name fields but never repeat input values.
  - **Alerts:** the four alerts and their documented severities, with Collector-down investigated first.
  - **Missing telemetry:** an incident when the Collector is down; expected only with explicit evidence (OTLP export disabled, backend not running, or no requests served yet); otherwise `needs-investigation`.
  - **Root cause:** `unknown` unless the evidence establishes it.
  - **Resolution:** `resolved` only with complete verification evidence (runbook section 8).
  - **Report:** a Markdown or JSON report following the runbook's incident template.
  - **Output files:** `--output` only creates a new file.
- **`custom-agent/tests/test_oncall_investigator.py`** (new, 367 lines, 32 tests; `ae8a0ab`). It covers:
  - all four alerts, and a drift check against the rules file;
  - Collector priority;
  - expected versus unexpected missing telemetry;
  - root cause and resolution rules;
  - malformed input and privacy restrictions;
  - the CLI, using temporary directories only.
- **`README.md`** (On-Call Agent section; not yet committed): the investigator, its input, supported alerts, prioritization, reports, CLI usage, boundaries, and verified results.
- **Documentation:** this entry.

### Boundaries

The investigator has none of the following:

- live telemetry connections (no Prometheus, Grafana, Loki, or Tempo queries);
- automatic triggering by alerts;
- remediation;
- database access or Docker operations;
- network or shell access;
- LLM calls.

It reads only the evidence file the developer names. It writes only an explicitly requested new report file.

### Manual Review and Corrections

- **Agent self-correction:** while reviewing its own tests before handing them over, Claude Code found that the import check passed `^`-anchored patterns to `assertNotRegex` without multiline matching. That would have checked only the first line of the source file. The pattern was corrected to use `(?m)`.
- **Outdated context:** while documenting the investigator, Claude Code initially relied on outdated Git and test context. It described the investigator as uncommitted and its tests as not yet run. The developer corrected this and supplied the verified results. The README was then updated using those results.
- **Developer review:** the developer reviewed the changes, ran the tests, verified the staged files, committed, pushed, and checked CI.

### Tests Executed

**Local (run by the developer):**

- Investigator tests: 32 of 32 passed.
- All custom-agent tests (`custom-agent/tests`): 38 of 38 passed.

**GitHub Actions (checked by the developer):**

- CI run #27 passed all five jobs.

**Claude Code** did not run tests in this entry's work, as instructed. For the README update it ran only `git diff --stat` and `git diff --check`; the check was clean.

### Human Oversight

- **Done by the developer:** reviewed the changes, ran the tests, verified the staged files, committed `ae8a0ab`, pushed it to `main`, and checked CI.
- **What Claude Code did not do:** stage, commit, push, or deploy.
- **What did not happen:**
  - no access to or changes in the development PostgreSQL database or the protected backups;
  - no Docker operations;
  - no Render changes;
  - no `.env` file or secret was read.

### Remaining Work

- **Not implemented** (none of these should be described as available):
  - live, read-only telemetry integration (Prometheus, Loki, Tempo);
  - operational alert triggering of the investigator;
  - any remediation.
- **Further verification:** the investigator has been exercised with synthetic evidence only, not against real alerts or a running monitoring stack.
- **Documentation:** commit the README On-Call Agent update. `docs/agent-extension-pack.md` and `docs/permissions.md` do not yet describe the investigator.
- **Render deployment** remains on hold.

### Outcome

CareerPilot now has a deterministic, read-only On-Call Investigator. It turns synthetic evidence for its four local Prometheus alerts into runbook-style incident reports, prioritizing Collector outages and separating expected missing telemetry from incidents. It is tested locally (32 of 32) and in CI (run #27). It does not read live telemetry, is not triggered by alerts, and does not remediate.

## Entry 015 — Read-Only Prometheus Alert Adapter

**Date:** October 26, 2026 (UTC)
**AI Coding Agent:** Claude Code (Claude Opus 5.5)
**Development Method:** Human-supervised, agent-assisted implementation
**Status:** Implemented, not committed. Adapter tests: 21 of 21 passed; full custom-agent suite: 59 of 59 passed. Both used mocked HTTP only. A live read-only query of the local Prometheus succeeded on October 26, 2026 (UTC). No CI run yet. Render deployment remains **on hold**.

### Objective

Add a separate, read-only adapter that takes a sanitized snapshot of the CareerPilot alerts the local Prometheus reports. It stays strictly separate from the synthetic-only On-Call Investigator (Entry 014).

### Tasks and Prompts (summarized)

1. **Implementation request.** The developer asked for a standard-library-only adapter:
   - HTTP GET only, to the fixed endpoint `http://127.0.0.1:9090/api/v1/alerts`;
   - no arbitrary URLs, redirects, proxies, credentials, or user-defined PromQL;
   - network access opt-in through an explicit flag, with no connection by default;
   - a short timeout and a bounded response size;
   - strict validation of the API status, alert list, the four allowlisted alerts, their severities, states, and timezone-aware `activeAt` timestamps;
   - no raw annotations, unexpected labels, secrets, request bodies, or resume content in output;
   - a sanitized snapshot labelled `source=live-prometheus` and `synthetic=false`;
   - no use of the synthetic-only investigator, and no resolution claims;
   - an empty snapshot, not a health conclusion, when no alerts are active;
   - mocked-HTTP tests only.

   Scope was exactly two new files, with no live requests.
2. **Documentation request.** Update `README.md` and this log.

### Context Supplied

- `AGENTS.md`.
- `custom-agent/oncall_investigator.py` and its tests, for conventions and to confirm the investigator rejects live snapshots.
- `monitoring/alerts/careerpilot.rules.yml`, for alert names and severities.
- For documentation: the README On-Call Agent section and this log.

### Files Changed

- **`custom-agent/prometheus_alert_adapter.py`** (new):
  - **Request:** `--connect` sends one GET with an `Accept` header only, through an opener that ignores environment proxies and refuses redirects. The timeout is 3 seconds, and responses are limited to 256 KiB and 100 alerts.
  - **Validation:** strict, as requested. Prometheus's nanosecond `activeAt` precision is truncated to microseconds and converted to UTC.
  - **Output:** a JSON snapshot on stdout. Each alert has only `alertname`, `severity`, `state`, and `active_at_utc`, with the Collector alert listed first. Notes state that the snapshot is not a health assessment, does not assess resolution, and is not investigator input.
  - **Exit codes:** `0` snapshot printed, `1` no `--connect`, `2` rejected. Error messages never quote response content.
- **`custom-agent/tests/test_prometheus_alert_adapter.py`** (new, 21 tests). It uses fake openers, and fake `urllib` transport handlers that exercise the real opener's redirect handling without connecting. It covers:
  - offline default and the request shape;
  - environment proxies and refused redirects;
  - sanitized output for all four alerts, and the empty snapshot;
  - rejection of the snapshot by the investigator;
  - malformed JSON, bad API status, and oversized responses;
  - unknown alerts, bad severities, states, and timestamps;
  - unexpected status or URL, and network failures;
  - a source-import check.
- **`README.md`:** a new "Prometheus Alert Adapter" subsection under On-Call Agent, and two reference links.
- **`docs/ai-development-log.md`:** this entry.

`oncall_investigator.py` and its tests were not modified.

### Manual Review and Corrections

- **Before the first test run,** Claude Code's own review fixed three test problems:
  - a helper call that would have raised `TypeError`;
  - an endpoint-count check that would also have counted the docstring URL;
  - a snapshot note whose wording clashed with the test that output never says "resolved".
- **The first test run** had 1 failure and 2 errors, all test defects:
  - `run_main` wrapped a real `urllib` opener inside the fake opener, so `open()` returned the opener instead of a response;
  - the proxy test expected a `ProxyHandler` to be present. `urllib` drops a `ProxyHandler({})` because it has no proxies, although passing it still replaces the environment-proxy default. The test now sets `HTTP_PROXY` and checks that no proxy handler exists.

  No adapter code changed as a result of these failures.
- **Developer review:** the developer reviewed the adapter and ran the live read-only query.

### Tests Executed

**Local, mocked HTTP only (run by Claude Code):**

- `python -m unittest discover -s custom-agent/tests -p "test_prometheus_alert_adapter.py" -v`: 21 of 21 passed after the corrections above.
- `python -m unittest discover -s custom-agent/tests`: 59 of 59 passed (the existing 38 plus the 21 new tests).
- `git diff --check`: clean.

**Live read-only query (October 26, 2026 UTC):**

- The query against the local Prometheus succeeded. It returned one firing `CareerPilotBackendTelemetryMissing` alert with severity `info`.
- **Interpretation:** the local backend was stopped at the time, which is a plausible explanation. This is not a proven cause, and it is not a production incident.

**GitHub Actions:** not yet run for this change.

### Human Oversight

- **Done by the developer:** reviewed the changes and ran the live query.
- **What Claude Code did not do:** make live requests, stage, commit, push, or deploy.
- **What did not happen:**
  - no access to or changes in PostgreSQL or the protected backups;
  - no changes to running containers or monitoring configuration;
  - no MCP or Render changes;
  - no `.env` file or secret was read.

### Limitations and Safety Constraints

- The adapter is read-only and local-only. It never connects without `--connect`, and only ever to the fixed endpoint.
- It reports only what Prometheus says is active. It does not diagnose root cause, verify recovery, or judge system health; an empty snapshot is not evidence of health.
- The snapshot is never investigator input. The investigator accepts synthetic evidence only and rejects live snapshots.
- No database, Docker, shell, file writes, or remediation.
- Strict validation means any unknown alert in Prometheus makes the whole response fail.

### Follow-up Work

- Commit the adapter, tests, and documentation, then confirm CI.
- `docs/agent-extension-pack.md` and `docs/permissions.md` do not yet describe the investigator or the adapter.
- **Not implemented:** linking live snapshots to investigation (it would need an explicit, reviewed design), operational alert triggering, and any remediation.
- **Render deployment** remains on hold.

### Outcome

CareerPilot has a read-only, opt-in Prometheus alert adapter. It produces sanitized live alert snapshots from the fixed local endpoint, tested with 21 mocked-HTTP tests (59 of 59 across the custom-agent suite), and it worked once against the live local Prometheus. It stays separate from the synthetic-only investigator and makes no health, root-cause, or recovery claims.

---

## Entry 016 — GitHub Issue #3 Agent Review

**Date:** October 25, 2026
**AI Coding Agent:** Claude Code
**Development Method:** Human-supervised, agent-assisted review
**Status:** Completed — read-only review; deployment remains blocked.

### Objective

Review public GitHub Issue #3 against CareerPilot's existing implementation and its 11 deployment acceptance criteria.

Issue: https://github.com/robanc/CareerPilot/issues/3

### Task and Agent Instructions

The developer directed Claude Code to review the issue, product specification, deployment documentation, configuration, backend safeguards, and existing test evidence.

The review was explicitly read-only. Database access, credential changes, file modifications, container operations, and deployment actions were prohibited.

### Context Reviewed

- `product-spec.md`
- `docs/deployment-render.md`
- `render.yaml`
- `.github/workflows/deploy.yml`
- Relevant backend safeguards and tests
- Public GitHub Issue #3

### Findings

- None of the 11 acceptance criteria could be confirmed as completed in the actual Render environment.
- Public-demo operating mode, read-only safeguards, database permission checks, fictional-data seeding, and deployment smoke tests are implemented or prepared.
- Render PostgreSQL authentication remains blocked by the reported SCRAM channel-binding failure.
- The deployment guide and README contain status inconsistencies.
- The README's CI information needs updating to reflect the five-job pipeline.

### Verification and Human Oversight

Claude Code fetched and reviewed the public issue and inspected repository files. No tests were executed during this review.

The developer reviewed the findings and published a factual summary as a comment on Issue #3:

https://github.com/robanc/CareerPilot/issues/3#issuecomment-6406935494

This documents actual agent participation in the public task tracker. Earlier deployment work is not retroactively attributed to Issue #3.

### Safety and Limitations

- No PostgreSQL access or modifications.
- No protected backup modifications.
- No credential or environment-variable changes.
- No container or Render deployment operations.
- No source-code changes during the agent review.
- Root cause of the SCRAM authentication failure remains unconfirmed.

### Outcome

The public task tracker now contains documented evidence of an AI agent reviewing Issue #3 against its acceptance criteria. The issue remains open and blocked pending Render Support confirmation.
