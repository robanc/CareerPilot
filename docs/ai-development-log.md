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
