# CareerPilot
AI-assisted job application tracking and career preparation platform

AI Dev Tools Zoomcamp 2026 capstone. Requirements: [`product-spec.md`](product-spec.md).
API contract: [`openapi.yaml`](openapi.yaml). Engineering rules: [`AGENTS.md`](AGENTS.md).

## Table of Contents

1. [Problem Description](#problem-description)
2. [Product Specification](#product-specification)
3. [Agent Team Specification](#agent-team-specification)
4. [Context Management](#context-management)
5. [Application](#application)
6. [Testing](#testing)
7. [Containerization](#containerization)
8. [Deployment](#deployment)
9. [CI/CD](#cicd)
10. [Observability](#observability)
11. [Alerting on User Impact](#alerting-on-user-impact)
12. [On-Call Agent](#on-call-agent)
13. [Reproducibility](#reproducibility)



## Problem Description

Job seekers often manage applications, interview schedules, resume versions, and job descriptions across spreadsheets, emails, and multiple job portals. This fragmented process makes it difficult to track application progress, prepare for interviews, and identify relevant skills for a particular opportunity.

**CareerPilot** is an AI-assisted development capstone that provides a centralized platform for organizing job applications and supporting career preparation.

The application allows users to:

- **Manage job applications:** Create, view, update, delete, search, and filter applications by company, job title, and status.
- **Monitor application progress:** View dashboard summaries, application status counts, upcoming interviews, and recently updated applications.
- **Track interviews:** Record interview dates, times, and preparation notes.
- **Compare resumes with job descriptions:** Receive a deterministic, keyword-based matching score from 0–100, including matched and missing skills. This is a heuristic, not an assessment of candidate suitability.
- **Manage saved resumes:** Save, edit, view, and delete resumes in the local Resume Library, then select a saved resume for matching against an existing job application.

### Expected Behavior

In local mode, CareerPilot provides a full-stack application using a React frontend, FastAPI backend, and PostgreSQL database. Job application records and saved resumes persist in PostgreSQL.

CareerPilot also includes a separate public demonstration mode designed to use fictional data and prevent modifications. In this mode, write operations are blocked and the Resume Library is unavailable.

The public demonstration deployment is currently pending completion of database provisioning and security verification.


## Product Specification

CareerPilot's requirements, MVP scope, user stories, and acceptance criteria are documented in [Product Specification](product-spec.md).

Development and outstanding work are tracked through the public [GitHub Issues tracker](https://github.com/robanc/CareerPilot/issues).

**Tracked issue:**
- [Issue #3 — Resolve Render PostgreSQL authentication and verify public demo](https://github.com/robanc/CareerPilot/issues/3) — Open; blocked pending Render Support. Includes explicit acceptance criteria and deployment verification requirements.

Coding-agent participation is documented separately in [AI Development Log](docs/ai-development-log.md). Any issue-specific agent activity will be linked to its actual implementation and verification evidence.


## Agent Team Specification

CareerPilot was developed using a human-supervised, AI-assisted development workflow. Claude Code serves as the primary coding agent, supported by a specialized security-review subagent, reusable skills, guardrails, and a deterministic release-auditing agent.

### Agent Roles and Responsibilities

| Team Member | Role | Responsibilities |
|---|---|---|
| Human Developer | Project owner and final approver | Defines requirements, reviews changes, authorizes protected operations, verifies tests, and approves commits, pushes, and deployments. |
| Claude Code | Primary coding agent | Assists with implementation, debugging, test development, documentation, and reviewing changes under project instructions. |
| Security Reviewer | Specialized subagent | Performs read-only security reviews of code changes against `AGENTS.md` and the project's security protections. |
| Release Auditor | Deterministic custom agent | Performs six reproducible release checks using approved read-only MCP tools and writes an audit log without recording submitted content. |

### Supporting Agent Components

- **Reusable skill:** `.agents/skills/careerpilot-safe-test-run/SKILL.md` — documents a controlled backend testing workflow.
- **Guardrail hook:** `agent-hooks/guard.py` — denies prohibited operations and requests approval for sensitive actions.
- **MCP server:** `mcp-server/careerpilot_mcp.py` — exposes three scoped, read-only tools for API inspection, project documentation access, and deterministic resume matching.
- **Permissions policy:** `docs/permissions.md` — defines allowed, approval-required, and prohibited actions.

### Team Collaboration Process

The intended development and review process is:

1. **Requirements:** The human developer defines the task and acceptance criteria using the product specification and project documentation.
2. **Implementation:** Claude Code assists with implementation while following `AGENTS.md`, `CLAUDE.md`, and the permission boundaries.
3. **Security review:** The specialized security reviewer can inspect relevant changes and report potential violations without modifying files.
4. **Testing:** Changes are validated using the project's tests and controlled testing procedures.
5. **Release auditing:** The deterministic release auditor can perform its six checks using scoped MCP tools and record audit evidence.
6. **Human approval:** The developer reviews results and explicitly authorizes protected operations, including commits, pushes, database changes, and deployments.

These components are available as part of the agent workflow; their existence does not imply that every component was invoked for every development task.

### Evidence and Documentation

- [Agent Extension Pack](docs/agent-extension-pack.md)
- [AI Development Log](docs/ai-development-log.md)
- [Agent Permissions](docs/permissions.md)
- [Project Instructions](AGENTS.md)
- [Claude Code Instructions](CLAUDE.md)


## Context Management

CareerPilot uses structured project documentation to provide coding agents with consistent requirements, engineering conventions, development workflows, and security boundaries.

The primary agent context file is [AGENTS.md](AGENTS.md), which describes the project architecture, technology stack, repository structure, coding standards, testing requirements, and definition of done.

### Modular Documentation

| Document | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Central project instructions, development workflow, coding standards, and security boundaries |
| [CLAUDE.md](CLAUDE.md) | Claude Code-specific instructions and operational constraints |
| [Product Specification](product-spec.md) | Product requirements, user stories, MVP scope, and acceptance criteria |
| [OpenAPI Contract](openapi.yaml) | Frontend/backend API contract and request/response definitions |
| [Agent Extension Pack](docs/agent-extension-pack.md) | Reusable skill, specialized subagent, guardrail hook, MCP server, and custom agent |
| [Agent Permissions](docs/permissions.md) | Allowed, approval-required, and prohibited agent operations |
| [AI Development Log](docs/ai-development-log.md) | Development prompts, changes, review decisions, tests, and corrections |
| [Render Deployment Guide](docs/deployment-render.md) | Deployment procedure, security verification, operational checks, and rollback |

### Context Management Process

1. **Requirements first:** Agents review `product-spec.md` before implementing features.
2. **API consistency:** Agents consult `openapi.yaml` when changing frontend/backend interfaces.
3. **Engineering guidance:** `AGENTS.md` defines development standards, testing requirements, and security boundaries.
4. **Specialized context:** Supporting documentation provides additional guidance for agent extensions, permissions, and deployment.
5. **Conflict resolution:** Agents report conflicting requirements rather than silently changing the specification.
6. **Verification and evidence:** Changes are reviewed, tested, and documented before being considered complete.

This modular approach helps keep agent instructions focused, supports reproducible development, and maintains human oversight of sensitive operations.


## Application

CareerPilot is a full-stack job application tracking platform built with React, FastAPI, and PostgreSQL.

### Application Components

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React, Vite | Job application management, dashboard, interview tracking, resume matching, and Resume Library interface |
| Backend | Python, FastAPI | REST API, input validation, application logic, and database operations |
| Database | PostgreSQL 16 | Persistent storage of job applications and saved resumes |
| Container orchestration | Docker Compose | Starts the frontend, backend, and database together |

### Run the Application Locally

After configuring the required PostgreSQL environment variables in `.env`, start the full application from the repository root:

```powershell
docker compose up --build --detach
```

The application is configured to run at:

- **Frontend:** http://127.0.0.1:8080
- **Backend:** http://127.0.0.1:8002
- **API documentation:** http://127.0.0.1:8002/docs

Docker Compose starts PostgreSQL, waits for the database health check before starting the backend, and starts the frontend container.

### End-to-End Functionality

CareerPilot supports the following workflows:

1. Create, view, update, delete, search, and filter job applications.
2. View dashboard summaries, application statuses, upcoming interviews, and recently updated applications.
3. Record interview dates, times, and preparation notes.
4. Compare resume text with job descriptions using a deterministic matching algorithm.
5. Save and manage resumes through the local Resume Library.

Application and saved-resume records are stored in PostgreSQL. The Docker Compose configuration uses a named volume (`postgres_data`) to preserve database files across ordinary container restarts.

### Implementation References

- [Docker Compose Configuration](docker-compose.yml)
- [Frontend Source](frontend/)
- [Backend Source](backend/)
- [API Contract](openapi.yaml)

The public demonstration environment is separate from the local application and remains pending database authentication and security verification.


## Testing

CareerPilot uses automated backend, frontend, and database integration tests to validate application functionality, API behavior, security controls, and persistence.

### Test Coverage

| Test Category | Framework / Tool | Purpose |
|---|---|---|
| Backend unit tests | Pytest | Validate application logic, input validation, and API behavior |
| Database integration tests | Pytest + PostgreSQL 16 | Verify database interactions, persistence, and security behavior |
| Frontend tests | Vitest + React Testing Library | Verify frontend components and application behavior |
| Code quality | ESLint | Check frontend code quality |
| Frontend build | Vite | Verify the production frontend build |
| CI verification | GitHub Actions | Run automated checks on repository changes |

### Backend Tests

Backend tests run against a separate, disposable PostgreSQL database rather than the local development database.

**1. Start the isolated test database:**

```powershell
docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait
```

**2. Run the complete backend test suite:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1
```

The test runner validates the test container's identity, health, port configuration, and database markers before executing Pytest. It does not start, stop, recreate, or remove containers.

Once the test database is running, the full backend test suite can be executed with a single command.

### Frontend Tests

From the repository root:

```powershell
cd frontend
npm ci
npm run lint
npm test
npm run build
```

The `npm test` command runs the frontend test suite using Vitest.

### Continuous Integration

CareerPilot's GitHub Actions CI pipeline runs automated verification for backend tests, frontend linting and tests, agent extensions, and Docker Compose configuration.

See [.github/workflows/ci.yml](.github/workflows/ci.yml) for the CI workflow definition.

### Testing Safety

- Backend tests use the dedicated `careerpilot_test` database.
- The backend test runner disables `.env` loading and isolates database environment variables.
- Tests must not run against the development or production database.
- The test runner refuses execution when its safety checks fail.

**Implementation references:**

- [Backend Test Runner](ops/test-backend.ps1)
- [Backend Tests](backend/tests/)
- [Frontend Test Configuration](frontend/package.json)
- [Test Database Configuration](docker-compose.test.yml)

### Additional Testing Details

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


## Containerization

CareerPilot uses Docker and Docker Compose to package and run the complete full-stack application locally.

### Container Architecture

| Service | Container Technology | Purpose |
|---|---|---|
| `frontend` | Node.js 24 build stage + Nginx | Builds and serves the React application, with Nginx configured for API reverse proxying |
| `backend` | Python 3.12 slim + Uvicorn | Runs the FastAPI REST API |
| `db` | PostgreSQL 16 Alpine | Stores job applications and saved resumes |

### Single-Command Startup

From the repository root, after configuring the required PostgreSQL environment variables in `.env`:

```powershell
docker compose up --build --detach
```

This command builds the frontend and backend images and starts all three services.

The backend waits until PostgreSQL passes its health check before starting. The frontend is configured to depend on the backend service.

### Local Service Addresses

| Service | Address |
|---|---|
| Frontend | http://127.0.0.1:8080 |
| Backend API | http://127.0.0.1:8002 |
| API documentation | http://127.0.0.1:8002/docs |
| PostgreSQL | 127.0.0.1:5432 |

All published service ports are bound to localhost.

### Database Persistence

PostgreSQL stores its data in the named Docker volume `postgres_data`. This preserves application records across ordinary container restarts and recreation when the volume is retained.

Do not use `docker compose down -v` if you need to preserve existing database records.

### Implementation References

- [Docker Compose Configuration](docker-compose.yml)
- [Backend Dockerfile](backend/Dockerfile)
- [Frontend Dockerfile](frontend/Dockerfile)
- [Nginx Configuration](frontend/nginx.conf)


## Deployment

CareerPilot's public demonstration environment is designed for deployment on Render. The deployment configuration and release procedures are prepared, but the public demo is not yet operational.

### Deployment Architecture

| Component | Render Resource | Purpose |
|---|---|---|
| Frontend | `careerpilot-web` — Static Site | Serves the React application |
| Backend | `careerpilot-api` — Docker Web Service | Runs FastAPI in `public_demo` mode |
| Database | `careerpilot-db` — PostgreSQL 16 | Stores fictional demonstration records |

The intended request flow is:

```text
Browser
   |
   v
careerpilot-web (Render Static Site)
   |
   | /api/* rewrite
   v
careerpilot-api (FastAPI, public_demo)
   |
   | SELECT-only database role
   v
careerpilot-db (PostgreSQL 16)
```

### Public Demo Security

The public demonstration is designed to:

- Use fictional job application data.
- Block application write operations.
- Disable the Resume Library.
- Restrict database access to a SELECT-only role.
- Reject startup if the database role has write privileges.
- Apply request-size limits and rate limiting.
- Require explicit human approval for deployment.

These safeguards must be verified before the public demo is made operational.

### Deployment Procedure

The deployment process is documented in the [Render Deployment Guide](docs/deployment-render.md).

It covers:

1. Provisioning Render services and PostgreSQL.
2. Verifying database credentials and role capabilities.
3. Creating the database schema and restricted reader role.
4. Seeding fictional demonstration data.
5. Configuring Render and GitHub deployment settings.
6. Running the approval-gated release workflow.
7. Performing smoke tests and security verification.
8. Rollback and emergency shutdown procedures.

### Current Deployment Status

**Status: Blocked — public demo not yet operational.**

The Render resources have been provisioned, but PostgreSQL authentication remains unresolved. An external connection attempt returned:

```text
FATAL: SCRAM channel binding check failed
```

A support request has been submitted to Render. Database schema provisioning, SELECT-only role verification, and end-to-end public demonstration testing remain pending.

The public demo must not be treated as ready for release until these checks have passed.

### Deployment References

- [Render Deployment Guide](docs/deployment-render.md)
- [Render Blueprint](render.yaml)
- [Deployment SQL Review Files](deploy/render/)
- [Deployment Workflow](.github/workflows/deploy.yml)
- [Deployment Tracking Issue #3](https://github.com/robanc/CareerPilot/issues/3)


## CI/CD

CareerPilot uses GitHub Actions for continuous integration and includes a separate, manually triggered deployment workflow for the Render public demonstration environment.

### Continuous Integration

The [CI workflow](.github/workflows/ci.yml) runs automatically on:

- Pull requests targeting `main`.
- Pushes to `main`.

It can also be started manually or called by the deployment workflow.

### CI Pipeline

| Job | Automated Checks |
|---|---|
| `backend-tests` | Python 3.12, Pytest, PostgreSQL 16 integration tests |
| `frontend` | Node.js 24, dependency installation, ESLint, Vitest, production build |
| `agent-extensions` | Guardrail hook, MCP server, custom agent, skill and subagent tests |
| `docker-build` | Docker Compose configuration validation and frontend/backend image builds |

The backend CI job uses an isolated, disposable PostgreSQL test database with fixed test-only credentials.

The workflow has read-only repository permissions and does not publish images or deploy application services.

### Deployment Workflow

The [Deploy workflow](.github/workflows/deploy.yml) provides a controlled release process for Render.

The configured release sequence is:

1. **Manual trigger:** Start the workflow from `main` and enter the confirmation text `DEPLOY`.
2. **CI verification:** Run the complete CI workflow against the selected commit.
3. **Production approval:** Use the GitHub `production` environment for a required human approval gate, once configured.
4. **Render deployment:** Trigger backend and frontend deployment hooks for the selected commit.
5. **Post-deployment verification:** Check that the expected commit is deployed and execute the Render smoke-test script.

Deployment credentials are designed to be stored as protected GitHub environment secrets rather than committed to the repository.

### Current CI/CD Status

- **Continuous integration:** Configured for pull requests and pushes to `main`.
- **Manual deployment workflow:** Implemented, but not yet verified through a successful public release.
- **Automatic development deployment:** Not implemented.
- **Production deployment:** Pending completion of Render database provisioning and security verification.

The project intentionally requires human approval for production deployment.

### Implementation References

- [CI Workflow](.github/workflows/ci.yml)
- [Deploy Workflow](.github/workflows/deploy.yml)
- [Render Smoke Test](ops/smoke-test-render.sh)
- [Render Deployment Guide](docs/deployment-render.md)
- [GitHub Actions Runs](https://github.com/robanc/CareerPilot/actions)

### Additional CI/CD Details

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


## Observability

CareerPilot currently provides basic application logging and operational health endpoints. A complete observability stack with correlated metrics, distributed tracing, and centralized dashboards has not yet been implemented.

### Existing Capabilities

| Capability | Implementation |
|---|---|
| Application logging | Python's standard `logging` module is used for backend startup warnings |
| Health check | `GET /health` returns `{"status": "ok"}` when the application is serving requests |
| Version identification | `GET /version` reports the deployed commit when `RENDER_GIT_COMMIT` is configured |
| Deployment verification | The Render smoke-test script checks deployment readiness and commit identity |

### Current Limitations

The following capabilities have not yet been implemented or verified:

- Structured JSON logging with shared request or trace identifiers.
- User journey metrics for application creation, status updates, and resume matching.
- Distributed tracing across frontend, backend, and database operations.
- Centralized collection, storage, and visualization of correlated telemetry.
- An observability dashboard for investigating application performance and errors.

The backend includes an OpenTelemetry API dependency, but the presence of this dependency does not establish an operational tracing system.

### Privacy and Security

Any future observability implementation should avoid recording resume contents, job descriptions, credentials, or other sensitive information in logs, metrics, or traces.

### Implementation References

- [FastAPI Application](backend/app/main.py)
- [Backend Dependencies](backend/requirements.txt)
- [Render Smoke Test](ops/smoke-test-render.sh)


## Alerting on User Impact

CareerPilot provides health-check endpoints and user-facing error messages, but automated operational alerting has not yet been configured or verified.

### Existing Capabilities

- **API health check:** `GET /health` provides an endpoint that can be used by an external monitoring service.
- **Render health-check configuration:** The backend service is configured to use `/health`.
- **Database readiness checks:** Docker Compose uses PostgreSQL health checks to determine when the database is ready.
- **User-facing errors:** The React frontend displays error messages when certain application operations fail.

These mechanisms support application health checks and error handling but do not constitute an automated operational alerting system.

### Current Limitations

CareerPilot does not yet have a verified alert that notifies an operator when the application becomes unavailable or experiences user-impacting failures.

Potential future improvements include external uptime monitoring, API error-rate alerts, and notifications to a designated operator.

### Implementation References

- [FastAPI Health Endpoint](backend/app/main.py)
- [Render Configuration](render.yaml)
- [Docker Compose Configuration](docker-compose.yml)
- [Deployment Smoke Test](ops/smoke-test-render.sh)


## On-Call Agent

CareerPilot includes development-focused agent extensions, but an automated on-call incident-response agent has not yet been implemented.

### Existing Agent Capabilities

The project includes:

- **Security Reviewer:** A specialized, read-only agent for reviewing security-sensitive changes.
- **Release Auditor:** A deterministic custom agent for evaluating release readiness.
- **Guardrail Hook:** Prevents certain unsafe agent operations.
- **Read-Only MCP Server:** Provides narrowly scoped tools for inspecting project information.

These components support safer development and release preparation. They are not connected to an operational alerting system and do not automatically remediate production incidents.

### Current Limitations

CareerPilot does not currently provide:

- An operational alert that activates an on-call agent.
- Automated incident investigation based on production telemetry.
- An agent that diagnoses and fixes user-impacting failures.
- Verified automated remediation with incident audit records.

Any future on-call agent should operate within explicit permission boundaries, maintain an audit trail, and require human approval before performing potentially destructive operations.

### Implementation References

- [Agent Extension Pack](docs/agent-extension-pack.md)
- [Agent Permissions](docs/permissions.md)
- [Security Reviewer](.agents/agents/security-reviewer.md)
- [Release Auditor](custom-agent/release_auditor.py)
- [AI Development Log](docs/ai-development-log.md)


## Reproducibility

CareerPilot can be built, run, and tested locally using Docker Compose, Python, and Node.js. The public Render deployment is not required to reproduce the working local application.

### Prerequisites

- Git
- Docker Desktop with Docker Compose
- Python 3.12 for backend testing
- Node.js 24 and npm for frontend testing

### 1. Clone the Repository

```bash
git clone https://github.com/robanc/CareerPilot.git
cd CareerPilot
```

### 2. Configure the Local Environment

Create a `.env` file in the repository root with the following variables:

```dotenv
POSTGRES_USER=careerpilot_local
POSTGRES_PASSWORD=replace_with_a_unique_local_password
POSTGRES_DB=careerpilot
```

Use local-only credentials. Do not commit `.env` or store real personal information in the application.

### 3. Start the Full Application

From the repository root:

```bash
docker compose up --build --detach
```

Docker Compose starts the PostgreSQL database, FastAPI backend, and React frontend served through Nginx.

| Service | Local Address |
|---|---|
| Frontend | http://127.0.0.1:8080 |
| Backend API | http://127.0.0.1:8002 |
| API documentation | http://127.0.0.1:8002/docs |
| API health check | http://127.0.0.1:8002/health |

The local database uses a persistent Docker volume, so application records survive normal container restarts.

### 4. Verify the Application

Open the frontend in a browser and test the following workflows:

1. Create a job application using fictional information.
2. View the application in the list and dashboard.
3. Edit its status and verify the dashboard updates.
4. Add an interview date and preparation notes.
5. Run resume matching with fictional resume and job-description text.
6. Save a fictional resume in the Resume Library and use it for matching.
7. Refresh the application and confirm that saved records persist.

These steps exercise the frontend, backend API, and PostgreSQL database together.

### 5. Run Backend Tests

Backend tests use a separate, disposable PostgreSQL 16 test container. They must not run against the local development database.

Start the isolated test database from the repository root:

```powershell
docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait
```

With the backend Python dependencies installed in a Python 3.12 environment, run the Windows test script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1
```

The test runner validates the isolated database configuration before executing Pytest. It does not start, recreate, or remove Docker containers.

### 6. Run Frontend Checks

From the repository root:

```powershell
cd frontend
npm ci
npm run lint
npm test
npm run build
```

These commands run frontend linting, unit tests, and the production build.

### 7. Run Agent Extension Tests

From the repository root, with Python 3.12:

```powershell
python -m unittest discover -s agent-hooks/tests
python -m unittest discover -s mcp-server/tests
python -m unittest discover -s custom-agent/tests
python -m unittest discover -s .agents/tests
```

These tests verify the guardrail hook, MCP server, custom agent, and reusable agent components.

### Known Limitations

- CareerPilot does not provide user authentication. Use fictional data only.
- The Resume Library is available in local mode but disabled in public demonstration mode.
- Resume matching is deterministic and keyword-based; its score is not an assessment of candidate suitability.
- The Render public demo remains blocked by PostgreSQL authentication and security provisioning requirements.
- Production deployment is not necessary to reproduce the local application or run the automated tests.

### Reproducibility References

- [Product Specification](product-spec.md)
- [Local Docker Compose Configuration](docker-compose.yml)
- [Isolated Test Database Configuration](docker-compose.test.yml)
- [Backend Test Runner](ops/test-backend.ps1)
- [CI Workflow](.github/workflows/ci.yml)
- [Agent Extension Documentation](docs/agent-extension-pack.md)


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
