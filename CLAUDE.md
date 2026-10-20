# CLAUDE.md

Guidance for Claude Code in the CareerPilot repository.

## Primary guidance

Read these first. They are the source of truth, in this order; this file does not repeat them.

1. `product-spec.md`: requirements and acceptance criteria.
2. `openapi.yaml`: the HTTP API contract (`/health`, `/config`, `/version`, `/applications`, `/applications/{id}`, `/dashboard`, `/resume/match`).
3. `AGENTS.md`: engineering workflow, coding rules, testing scope, and security boundaries.

If they conflict, report the conflict instead of choosing one.

## Architecture

    React/Vite frontend  ->  FastAPI backend  ->  PostgreSQL 16
    (frontend/)              (backend/app/)       (SQLAlchemy, psycopg 3)

- **Frontend:** React and Vite (Node 24). In Docker it is built and served by nginx, which proxies `/api/` to the backend.
- **Backend:** FastAPI on Python 3.12. The app is imported as `backend.app.main:app`. Routers, schemas, services, and models live under `backend/app/`. `init_db()` creates any missing tables on startup and never drops them.
- **Database:** PostgreSQL. Connection settings come from `POSTGRES_*` environment variables (locally from `.env`). Tests use the separate `careerpilot_test` database.
- **Docker Compose:** `docker-compose.yml` runs `db`, `backend`, and `frontend`. All ports are bound to `127.0.0.1`: db 5432, backend 8002, frontend 8080.
- **CI:** `.github/workflows/ci.yml` runs backend tests, frontend lint, tests, and build, and Docker image builds. It does not deploy.
- **Deployment:** `.github/workflows/deploy.yml` (manual and approval-gated) releases the read-only public demo to Render; see `docs/deployment-render.md`.

## Commands

Run the backend tests from the repository root, against the isolated test container (`docker-compose.test.yml`, 127.0.0.1:5433), which must already be running and healthy. The runner checks the container and the cluster identity, disables `.env` loading, and sets the test connection variables; `backend/tests/conftest.py` refuses any other endpoint. Plain `pytest` also fails to import the `backend` package.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1
```

Frontend (from `frontend/`):

```bash
npm run lint
npm test
npm run build
```

## Working rules

- **Before committing:** run the tests relevant to the change and review the full `git diff`.
- **Human approval:** AI-generated changes need human review and approval before any commit or push. Do not commit or push unless the developer explicitly asks.
- **Secrets:** never read, print, or expose `.env`, credentials, tokens, or private keys. Do not echo environment variables or command output that may contain them. Use `--quiet` with `docker compose config`, because the full output prints `.env` values.
- **Database safety:** never run destructive database operations without explicit approval. This includes `DROP`, `TRUNCATE`, bulk `DELETE`, `drop_all`, `docker compose down -v`, and removing the `postgres_data` volume. Never point tests or cleanup at the development database; the guard in `backend/tests/conftest.py` must stay in place.
- **Development log:** record significant AI-assisted work in `docs/ai-development-log.md`, as `AGENTS.md` describes. Report only checks that actually ran.
