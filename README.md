# CareerPilot
AI-assisted job application tracking and career preparation platform

AI Dev Tools Zoomcamp 2026 capstone. Requirements: [`product-spec.md`](product-spec.md).
API contract: [`openapi.yaml`](openapi.yaml). Engineering rules: [`AGENTS.md`](AGENTS.md).

## Features (MVP)

- **Applications:** create, view, edit, and delete job applications (company, title, date,
  status, job URL, description, notes), with search by company or title and a status filter.
- **Dashboard:** totals, counts by status, upcoming interviews in chronological order, and
  recently updated applications, each linking to its record.
- **Interview tracking:** interview date and time plus preparation notes on each application.
  Past interviews drop off the upcoming list.
- **Resume matching:** paste a resume and a job description to get a 0-100 score with matched
  and missing skills. It is labeled as a deterministic, keyword-based **heuristic**, not an
  assessment of suitability. Submitted text is neither stored nor logged.
- **Resume Library (local mode only):** save, view, edit, and delete resumes.
  Select a saved resume and an existing job application to run resume matching.
  Saved resumes are stored in the local database. The library is unavailable
  in public demo mode.
- **Read-only public demo mode** (`CAREERPILOT_MODE=public_demo`): writes are refused, data is
  fictional, and requests are rate limited and size limited. The UI hides write actions and
  shows a banner.

## Architecture

    React/Vite frontend  ->  FastAPI backend  ->  PostgreSQL 16
    (frontend/)              (backend/app/)       (SQLAlchemy, psycopg 3)

- **Frontend:** all API calls go through one module, `frontend/src/services/api.js`. In Docker, nginx
  serves the build and proxies `/api/` to the backend.
- **Backend:** routers, schemas, services, and models live under `backend/app/`.
  - `limits.py`: rate limits and the request body size cap (public demo only).
  - `readonly.py`: write blocking (public demo only).
  - `settings.py`: operating-mode selection.
- **Database:** PostgreSQL. Local mode creates missing tables on startup; the public demo never
  creates tables, and it refuses to start unless its database role is SELECT-only.

## Local setup

Requirements: Docker Desktop, Python 3.12, and Node.js 24.

1. Create a `.env` file in the repository root (it is git-ignored) with `POSTGRES_USER`,
   `POSTGRES_PASSWORD`, and `POSTGRES_DB` for your local development database. Never commit
   it, and use only fictional data.
2. Start the full stack:

       docker compose up --build --detach

   - Frontend: http://127.0.0.1:8080
   - API: http://127.0.0.1:8002 (for example `/health`)

   All ports are bound to 127.0.0.1 only.
3. To run the frontend dev server against that backend instead:

       cd frontend && npm ci && VITE_API_URL=http://127.0.0.1:8002 npm run dev

## Testing

**Backend.** The tests run only against a disposable, isolated PostgreSQL 16 container on
127.0.0.1:5433 (`docker-compose.test.yml`), never the development database.

- **Start the container once,** yourself:

      docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait

- **Then run the tests** from the repository root, with the backend virtual environment's
  Python first on PATH (Windows):

      powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1

- **What the runner does** (`ops/test-backend.ps1`):
  - It uses only that container, which must already be running and healthy; it never creates,
    starts, or recreates containers.
  - It verifies the container's configuration and the cluster's identity.
  - It disables `.env` loading and sets the test connection variables.
- **Safety net in the tests themselves:** `backend/tests/conftest.py` refuses any database
  endpoint other than 127.0.0.1:5433.

**Frontend** (Vitest with jsdom and a mocked API, so no backend is needed):

    cd frontend && npm ci && npm run lint && npm test && npm run build

**Agent extensions** (standard library only; no network, database, or dependencies):

    python -m unittest discover -s agent-hooks/tests
    python -m unittest discover -s mcp-server/tests
    python -m unittest discover -s custom-agent/tests
    python -m unittest discover -s .agents/tests
    python custom-agent/release_auditor.py

## CI/CD

GitHub Actions runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml) on pushes and pull requests to `main`, and on demand via **Run workflow** (`workflow_dispatch`).

| Job | What it checks |
|---|---|
| Backend tests | Installs `backend/requirements.txt` on Python 3.12, starts the isolated PostgreSQL 16 test container (`docker-compose.test.yml`, 127.0.0.1:5433), and runs `python -m pytest backend/tests` |
| Frontend | `npm ci`, `npm run lint`, `npm test` (Vitest), and `npm run build` on Node.js 24 |
| Agent extensions | Guardrail hook, MCP server, custom agent, and skill/subagent checks (`unittest`, Python 3.12) |
| Docker build | Validates `docker-compose.yml` and builds the backend and frontend images |

The pipeline uses temporary CI-only database credentials, a read-only `GITHUB_TOKEN`, and no repository secrets. It does not push images or deploy.

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) is the only way to release. You
start it by hand, and it runs four stages in order:

1. **guard:** `main` only, with the confirmation `DEPLOY` typed in.
2. **verify:** reruns all of the CI checks above on that commit.
3. **deploy:** waits for approval in the `production` environment, then triggers the Render
   deploy hooks.
4. **smoke:** refuses to pass until the API and the static site both report the commit being
   released (`/version`, `/version.json`), then runs read-only safety checks.

## Deployment (prepared, not yet performed)

The public read-only demo targets Render: the Blueprint [`render.yaml`](render.yaml), the release workflow described above, and the provisioning SQL drafts in [`deploy/render/`](deploy/render/). The full procedure, rollback, and the proxy and rate-limiting notes are in [docs/deployment-render.md](docs/deployment-render.md). `public_demo` is **not safe to deploy** until that procedure is complete.

## Security and data handling

- **Fictional data only:** the MVP has no authentication. Use fictional data everywhere; the
  public demo shows only the fictional seed (`backend/scripts/seed_demo_data.py`).
- **Resume privacy:** pasted resume text and job descriptions submitted for
  matching are not stored or logged by the matching feature. Saved resumes
  in the local-only Resume Library are intentionally persisted in PostgreSQL.
  The Resume Library is disabled in public demo mode. Matching inputs are
  limited to 20,000 characters per field.
- **Public demo protections:** writes are blocked twice, by the middleware and by a check on
  each write route. Sessions start read-only, and startup verifies that the database role is
  strictly SELECT-only. Rate limiting and a 256 KiB request cap apply.
- **Hiding buttons is not a security boundary:** the UI hides write actions in the demo, but
  the backend enforces every rule on its own.
- **Secrets:** none are committed. Deployment credentials live only in Render and in GitHub
  environment secrets.

## AI-assisted development

CareerPilot was built with Claude Code under human supervision. Every commit, push, database
change, and deployment step required explicit approval from the developer.

- [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md): the instructions and security
  boundaries given to the coding agent.
- [`docs/ai-development-log.md`](docs/ai-development-log.md): per-feature evidence (prompts,
  files changed, review, tests run, and corrections).
- [`docs/agent-extension-pack.md`](docs/agent-extension-pack.md): the agent extension pack.
  - Reusable skill and specialized subagent: `.agents/`.
  - Guardrail hook: `agent-hooks/`, wired in `.claude/settings.json`.
  - Scoped MCP server: `mcp-server/`, wired in `.mcp.json`.
  - Auditable custom agent: `custom-agent/`.
- [`docs/permissions.md`](docs/permissions.md): what agents may do, what needs approval, and
  how each rule is enforced.
