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



## Product Specification

CareerPilot is an AI-assisted job application tracking and career preparation platform designed to help job seekers organize applications, monitor their progress, prepare for interviews, and compare resumes with job descriptions.

The product provides application management with search and status filtering, a dashboard showing application activity and upcoming interviews, interview scheduling and preparation notes, deterministic keyword-based resume matching, and a local Resume Library. Application records and saved resumes persist in PostgreSQL.

The MVP requirements, functional specifications, user stories, expected behavior, scope, and feature-level acceptance criteria are documented in the [Product Specification](product-spec.md). The application also includes a separate read-only public demonstration mode designed for fictional data; its Render deployment is on hold.

Development and outstanding work are tracked through the public [GitHub Issues tracker](https://github.com/robanc/CareerPilot/issues).

**Task Tracked issue:**
- [Issue #3 — Resolve Render PostgreSQL authentication and verify public demo](https://github.com/robanc/CareerPilot/issues/3) — Open; on hold pending Render Support. Includes explicit acceptance criteria and deployment verification requirements.
  - [Claude Code review of Issue #3](https://github.com/robanc/CareerPilot/issues/3#issuecomment-6406935494): a read-only comparison of the implementation with the issue's acceptance criteria. The issue remains open.

Coding-agent participation is documented separately in [AI Development Log](docs/ai-development-log.md). Issue-specific agent activity is linked to its evidence; the Issue #3 review is recorded in Entry 016.



## Agent Team Specification

CareerPilot was developed using a human-supervised, AI-assisted development workflow. Claude Code serves as the primary coding agent, supported by a specialized security-review subagent, reusable skills, guardrails, and a deterministic release-auditing agent.

### Agent Roles and Responsibilities

| Team Member | Role | Responsibilities |
|---|---|---|
| Human Developer | Project owner and final approver | Defines requirements, reviews changes, authorizes protected operations, verifies tests, and approves commits, pushes, and deployments. |
| Claude Code | Primary coding agent | Assists with implementation, debugging, test development, documentation, and reviewing changes under project instructions. |
| Security Reviewer | Specialized subagent | Performs read-only security reviews of code changes against `AGENTS.md` and the project's security protections. |
| Release Auditor | Deterministic custom agent | Performs six reproducible release checks using approved read-only MCP tools and writes an audit log without recording submitted content. |
| On-Call Investigator | Deterministic custom agent (synthetic-only) | Turns synthetic alert evidence into runbook-style incident reports; read-only and non-remediating (see [On-Call Agent](#on-call-agent)). |
| On-Call Responder | Deterministic custom agent (synthetic sandbox only) | Wakes on synthetic alert events and applies one allowlisted, verified, reversible repair to a disposable sandbox; never touches real services (see [On-Call Agent](#on-call-agent)). |

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

Docker Compose starts PostgreSQL, waits for the database health check before starting the backend, and starts the frontend container. Service addresses are listed under [Local Service Addresses](#local-service-addresses); the frontend runs at http://127.0.0.1:8080.

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

The public demonstration environment is separate from the local application; its deployment is on hold (see [Deployment](#deployment)).



## Testing

CareerPilot uses automated backend, frontend, database integration, agent extension, and alert rule tests to validate application functionality, API behavior, security controls, and persistence. All tests use synthetic or fictional data.

### Test Coverage

| Test Category | Framework / Tool | Purpose |
|---|---|---|
| Backend unit tests | Pytest | Validate application logic, input validation, and API behavior |
| Observability tests | Pytest | Verify request IDs, structured request logging, Prometheus HTTP metrics, and access rules for the local `/metrics` endpoint |
| Database integration tests | Pytest + PostgreSQL 16 | Verify database interactions, persistence, and security behavior |
| Frontend tests | Vitest + React Testing Library | Verify frontend components and application behavior |
| Code quality | ESLint | Check frontend code quality |
| Frontend build | Vite | Verify the production frontend build |
| Agent extension tests | `unittest` | Guardrail hook, MCP server, release auditor, On-Call Investigator (synthetic input), Prometheus alert adapter (mocked HTTP), On-Call Responder (disposable synthetic sandboxes), skills and subagents |
| Alert rule tests | `promtool` | Synthetic time-series tests for the four Prometheus alert rules |
| CI verification | GitHub Actions | Run automated checks on repository changes |

### Backend Tests

Backend tests run only against a disposable, isolated PostgreSQL 16 container on 127.0.0.1:5433 (`docker-compose.test.yml`), never the development database.

**1. Start the isolated test database once:**

```powershell
docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait
```

**2. Run the complete backend test suite** from the repository root, with the backend virtual environment's Python 3.12 first on PATH (Windows):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1
```

The runner (`ops/test-backend.ps1`) uses only that container, which must already be running and healthy; it never starts, stops, recreates, or removes containers. It verifies the container's configuration and the cluster's identity, disables `.env` loading, and sets the test connection variables. As a second safety net, `backend/tests/conftest.py` refuses any database endpoint other than 127.0.0.1:5433.

### Frontend Tests

Vitest runs with jsdom and a mocked API, so no backend is needed. From the repository root:

```powershell
cd frontend
npm ci
npm run lint
npm test
npm run build
```

### Agent Extension Tests

With Python 3.12, after installing `backend/requirements.txt` (the MCP server imports backend modules that need the OpenTelemetry dependencies):

```powershell
python -m unittest discover -s agent-hooks/tests
python -m unittest discover -s mcp-server/tests
python -m unittest discover -s custom-agent/tests
python -m unittest discover -s .agents/tests
python custom-agent/release_auditor.py
```

The On-Call Investigator tests use synthetic input only, and the Prometheus alert adapter tests use mocked HTTP responses only.

### Continuous Integration

All of these suites, plus the `promtool` alert rule checks, run in GitHub Actions. See [CI/CD](#cicd) for the pipeline and the latest verified run.

### Testing Safety

- Tests and demonstrations use synthetic or fictional data only. Tests must never read or alter existing development database records.
- Backend tests use the dedicated `careerpilot_test` database.
- The backend test runner disables `.env` loading and isolates database environment variables.
- Tests must not run against the development or production database.
- The test runner refuses execution when its safety checks fail.

**Implementation references:**

- [Backend Test Runner](ops/test-backend.ps1)
- [Backend Tests](backend/tests/)
- [Frontend Test Configuration](frontend/package.json)
- [Test Database Configuration](docker-compose.test.yml)
- [Backend Test Safety Guard](backend/tests/conftest.py)
- [Custom Agent Tests](custom-agent/tests/)



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

CareerPilot's public demonstration environment is designed for deployment on Render. The deployment configuration and release procedures are prepared, but the public deployment is **on hold** and the public demo is not operational.

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

**Status: ON HOLD — public demo not operational.**

The Render resources have been provisioned, but PostgreSQL authentication remains unresolved. An external connection attempt returned:

```text
FATAL: SCRAM channel binding check failed
```

The root cause has not been confirmed. A support request has been submitted to Render, and the work is tracked in [Issue #3](https://github.com/robanc/CareerPilot/issues/3), which remains open. The [Claude Code review of Issue #3](https://github.com/robanc/CareerPilot/issues/3#issuecomment-6406935494) compares the prepared implementation with the issue's acceptance criteria.

Not yet completed or verified on Render:

- Database authentication and TLS connection.
- Schema provisioning and the SELECT-only demo role.
- Fictional seed data.
- The GitHub `production` environment approval configuration and deployment secrets.
- A successful release, the post-deployment smoke tests, and a working public URL.

No database provisioning or deployment will be performed until Render Support confirms that authentication and the role work. The public demo must not be treated as ready for release until these checks have passed.

### Deployment References

- [Render Deployment Guide](docs/deployment-render.md)
- [Render Blueprint](render.yaml)
- [Deployment SQL Review Files](deploy/render/)
- [Deployment Workflow](.github/workflows/deploy.yml)
- [Deployment Tracking Issue #3](https://github.com/robanc/CareerPilot/issues/3)
- [Claude Code Review of Issue #3](https://github.com/robanc/CareerPilot/issues/3#issuecomment-6406935494)



## CI/CD

CareerPilot uses GitHub Actions for continuous integration and includes a separate, manually triggered deployment workflow for the Render public demonstration environment.

### Continuous Integration

The [CI workflow](.github/workflows/ci.yml) runs automatically on:

- Pull requests targeting `main`.
- Pushes to `main`.

It can also be started manually (`workflow_dispatch`) or called by the deployment workflow.

### CI Pipeline

| Job (as shown in GitHub Actions) | Automated Checks |
|---|---|
| Backend tests (pytest + PostgreSQL 16) | Installs `backend/requirements.txt` on Python 3.12, starts the isolated PostgreSQL 16 test container (`docker-compose.test.yml`, 127.0.0.1:5433), and runs `python -m pytest backend/tests` |
| Frontend lint and build | `npm ci`, `npm run lint`, `npm test` (Vitest), and `npm run build` on Node.js 24 |
| Agent extension tests | Guardrail hook, MCP server, custom agent (including the On-Call Investigator, Prometheus alert adapter, and On-Call Responder tests), and skill/subagent checks (`unittest`, Python 3.12) |
| Monitoring config and alert rule validation | `promtool check config`, `check rules`, and `test rules` from the pinned Prometheus image |
| Docker image build verification | Validates `docker-compose.yml` and builds the backend and frontend images |

The pipeline uses fixed, test-only database credentials, a read-only `GITHUB_TOKEN`, and no repository secrets. It does not push images or deploy.

### Latest Verified CI Run

GitHub Actions CI run #32, on commit `54ea8571d90363f86fdd2ebd20b2f30c29e96376`, passed all five jobs (see the [CI workflow runs](https://github.com/robanc/CareerPilot/actions/workflows/ci.yml)):

- Monitoring config and alert rule validation
- Agent extension tests
- Docker image build verification
- Backend tests (pytest + PostgreSQL 16)
- Frontend lint and build

In that run, the Linux custom-agent suite reported "Ran 90 tests" and "OK", with no skipped tests.

Historical evidence, superseded by run #32: run #21 passed the four jobs that existed then (commit `3ea8ed6`), and runs #23, #24, #25, #27, and [#30](https://github.com/robanc/CareerPilot/actions/runs/40260769434) (commit `af533c3`) passed all five jobs.

### Deployment Workflow

The [Deploy workflow](.github/workflows/deploy.yml) is the only way to release. It is started by hand and runs four stages in order:

1. **guard:** `main` only, with the confirmation text `DEPLOY` typed in.
2. **verify:** reruns the complete CI workflow on that commit.
3. **deploy:** waits for approval in the GitHub `production` environment, then triggers the Render deploy hooks for that commit.
4. **smoke:** refuses to pass until the API and the static site both report the commit being released (`/version`, `/version.json`), then runs read-only safety checks (`ops/smoke-test-render.sh`).

The approval gate depends on the `production` environment being configured with required reviewers before the first release; that configuration has not been completed or verified. Deploy hook URLs are credentials and are meant to be stored only as `production` environment secrets, never in the repository.

### Current CI/CD Status

- **Continuous integration:** Operational. Latest verified run: #32, all five jobs passed (see the [CI workflow runs](https://github.com/robanc/CareerPilot/actions/workflows/ci.yml)).
- **Manual deployment workflow:** Implemented.
- **Automatic deployment:** The project intentionally requires human approval for production deployment.
- **Production deployment:** On hold (see [Deployment](#deployment)).

### Implementation References

- [CI Workflow](.github/workflows/ci.yml)
- [Deploy Workflow](.github/workflows/deploy.yml)
- [Render Smoke Test](ops/smoke-test-render.sh)
- [Render Deployment Guide](docs/deployment-render.md)
- [GitHub Actions Runs](https://github.com/robanc/CareerPilot/actions)
- [CI Workflow Runs (latest verified: #32)](https://github.com/robanc/CareerPilot/actions/workflows/ci.yml)



## Observability

CareerPilot includes a locally validated observability stack using OpenTelemetry, Prometheus, Grafana, Loki, and Tempo. The implementation provides HTTP request metrics, structured application logs with request and trace identifiers, backend tracing, and four locally evaluated Prometheus alert rules.

The monitoring stack runs separately from the application and PostgreSQL database using `monitoring/docker-compose.yml`. It is local-only: production observability and production alert delivery have not been deployed or verified.

### Implemented Capabilities

| Capability | Implementation |
|---|---|
| Application health | `GET /health` provides an application health check |
| Version identification | `GET /version` identifies the deployed commit when configured |
| HTTP metrics | Prometheus-compatible request counts and duration metrics |
| OpenTelemetry | Backend instrumentation and OTLP telemetry export |
| Backend tracing | Tempo stores backend `http.request` and `resume.match` spans |
| Structured logging | JSON HTTP logs include request and trace identifiers without request-body contents |
| Centralized visualization | Grafana provides access to Prometheus metrics, Loki logs, and Tempo traces |
| Log–trace correlation | Backend HTTP logs carry the `trace_id` of their trace; matching IDs were checked locally with synthetic requests (see [Monitoring Documentation](monitoring/README.md)) |
| Alert rules | Four local Prometheus rules with synthetic `promtool` tests (see [Alerting on User Impact](#alerting-on-user-impact)) |
| Automated validation | 10 observability tests passed locally |
| CI verification | GitHub Actions CI run #32 passed all five jobs, including monitoring configuration and alert rule validation (see the [CI workflow runs](https://github.com/robanc/CareerPilot/actions/workflows/ci.yml)) |

### Local Monitoring Setup

Start the independent monitoring stack:

```powershell
docker compose -p careerpilot-monitoring -f monitoring/docker-compose.yml up -d
```

Local monitoring interfaces:

| Service | Address |
|---|---|
| Grafana | http://127.0.0.1:3000 |
| Prometheus | http://127.0.0.1:9090 |
| Tempo | http://127.0.0.1:3200 |
| Loki | http://127.0.0.1:3100 |

OpenTelemetry export is enabled only when `CAREERPILOT_OTLP_ENABLED=true` is configured for the backend.

For detailed setup, telemetry queries, validation, and troubleshooting, see [Monitoring Documentation](monitoring/README.md).

### Current Limitations

- The monitoring stack has been validated locally but has not been deployed to production.
- Correlation has been checked only between backend logs and backend traces. End-to-end tracing and correlation across frontend, backend, and database operations have not been verified.
- Production alert delivery is not configured: there is no Alertmanager, notification channel, or production alerting.
- Business-level metrics for all job application workflows have not been verified.
- Local Prometheus alert rules and a manual incident response runbook are in place; see [Alerting on User Impact](#alerting-on-user-impact). No alert notifications are configured. Automated incident response exists only as a synthetic sandbox demonstration, and no real alert triggers it (see [On-Call Agent](#on-call-agent)).

### Privacy and Security

Observability instrumentation avoids recording resume contents, job descriptions, credentials, and request bodies in telemetry. Monitoring services are bound to local interfaces for development use.

### Implementation References

- [Monitoring Documentation](monitoring/README.md)
- [Monitoring Docker Compose](monitoring/docker-compose.yml)
- [OpenTelemetry Instrumentation](backend/app/observability.py)
- [Resume Matching Service](backend/app/services/resume_matcher.py)
- [Backend Dependencies](backend/requirements.txt)
- [Render Smoke Test](ops/smoke-test-render.sh)



## Alerting on User Impact

CareerPilot provides health-check endpoints, user-facing error messages, and four local Prometheus alert rules for backend errors, latency, and telemetry availability. Alerts are evaluated by the local monitoring stack only; no notifications are sent and production alerting is not configured.

### Existing Capabilities

- **API health check:** `GET /health` provides an endpoint that can be used by an external monitoring service.
- **Render health-check configuration:** The backend service is configured to use `/health`.
- **Database readiness checks:** Docker Compose uses PostgreSQL health checks to determine when the database is ready.
- **User-facing errors:** The React frontend displays error messages when certain application operations fail.

These mechanisms support application health checks and error handling but do not by themselves provide alerting. Alerting comes from the separately configured local Prometheus rules described below.

### Local Prometheus Alerts

The local Prometheus instance evaluates these rules against the backend's OpenTelemetry metrics, exported through the OpenTelemetry Collector:

| Alert | Condition | For | Severity |
|---|---|---|---|
| `CareerPilotHigh5xxRate` | 5xx responses above 5% of requests over 5 minutes, with at least 10 requests | 5m | warning |
| `CareerPilotHighAverageLatency` | Average request duration above 0.5 seconds | 10m | warning |
| `CareerPilotBackendTelemetryMissing` | No backend request metrics in Prometheus | 5m | info |
| `CareerPilotOtelCollectorDown` | Prometheus cannot scrape the OpenTelemetry Collector | 2m | warning |

Firing alerts are visible at http://127.0.0.1:9090/alerts and through Grafana. `CareerPilotBackendTelemetryMissing` is expected to fire locally when OpenTelemetry export is disabled or the backend is not running.

### Alert Validation

- **Synthetic rule tests:** `promtool test rules` runs 9 test cases on synthetic time series, with no running services or database. The tests check that each alert fires after its `for` duration and stays inactive below its threshold.
- **Local validation:** `promtool check config`, `check rules`, and `test rules` passed locally.
- **GitHub Actions:** the "Monitoring config and alert rule validation" CI job runs the same three `promtool` checks. It passed in the latest verified CI run #32 (see the [CI workflow runs](https://github.com/robanc/CareerPilot/actions/workflows/ci.yml)); historical runs #23, #24, #25, and #30 also passed all five jobs.

### Incident Response

[`monitoring/INCIDENT_RESPONSE.md`](monitoring/INCIDENT_RESPONSE.md) is a manual runbook for the four alerts. It covers:

- triage;
- investigation in Prometheus, Grafana, Loki, and Tempo;
- expected versus unexpected missing telemetry;
- recovery verification, escalation, and an incident report template.

Restarts and remediation of real services require developer approval. The runbook's section 12 describes the separate, synthetic-only sandbox responder.

### Current Limitations

- **No Alertmanager or notifications:** alerts must be checked manually, and no operator is notified.
- **No production alerting:** the alerts cover the local monitoring stack only, not the Render deployment.
- **Limited live verification:** alert logic is verified with synthetic `promtool` tests. On the running local stack, only `CareerPilotBackendTelemetryMissing` has been observed firing, once, through the read-only Prometheus alert adapter on October 26, 2026 (UTC). The other three alerts have not been observed firing live.
- **No external uptime monitoring.**

Potential future improvements include external uptime monitoring, notifications to a designated operator, and production alerting.

### Implementation References

- [FastAPI Health Endpoint](backend/app/main.py)
- [Render Configuration](render.yaml)
- [Docker Compose Configuration](docker-compose.yml)
- [Deployment Smoke Test](ops/smoke-test-render.sh)
- [Monitoring Documentation](monitoring/README.md)
- [Prometheus Alert Rules](monitoring/alerts/careerpilot.rules.yml)
- [Alert Rule Tests](monitoring/alerts/tests/careerpilot.rules.test.yml)
- [Incident Response Runbook](monitoring/INCIDENT_RESPONSE.md)



## On-Call Agent

CareerPilot includes development-focused agent extensions, a manual [incident response runbook](monitoring/INCIDENT_RESPONSE.md) for its local alerts, a deterministic, read-only On-Call Investigator, and a **synthetic-only** On-Call Responder. The responder demonstrates alert-activated repair inside a disposable synthetic sandbox. No agent is woken by real alerts, and none remediates the real application or any real service.

### Existing Agent Capabilities

The project includes:

- **Security Reviewer:** A specialized, read-only agent for reviewing security-sensitive changes.
- **Release Auditor:** A deterministic custom agent for evaluating release readiness.
- **Guardrail Hook:** Prevents certain unsafe agent operations.
- **Read-Only MCP Server:** Provides narrowly scoped tools for inspecting project information.
- **On-Call Investigator:** A deterministic custom agent that produces runbook-style incident reports from synthetic alert evidence (see below).
- **On-Call Responder (synthetic only):** A deterministic agent that wakes on synthetic alert events and repairs a disposable synthetic sandbox (see below).

These components support safer development and release preparation. They are not connected to an operational alerting system and do not remediate real or production incidents.

### Manual Incident Response

The local Prometheus alerts are handled by a developer, or an AI agent under developer supervision, following [`monitoring/INCIDENT_RESPONSE.md`](monitoring/INCIDENT_RESPONSE.md). The runbook limits investigation to read-only steps and requires developer approval for every restart and remediation of a real service. No agent is triggered by a real alert.

### On-Call Investigator

[`custom-agent/oncall_investigator.py`](custom-agent/oncall_investigator.py) is a deterministic agent with no LLM. A developer runs it by hand against one local JSON file of synthetic alert evidence. It validates the file and produces an incident report that follows the runbook.

- **Input:** a strict JSON schema (`schema_version: 1`) that must declare `"synthetic": true`. It lists alerts with their state and UTC timestamps, plus optional evidence: OTLP state, backend and Collector status, observations, actions, root cause, and verification checks.
- **Supported alerts:** exactly the four Prometheus alerts and their documented severities:
  - `CareerPilotOtelCollectorDown` (warning);
  - `CareerPilotHigh5xxRate` (warning);
  - `CareerPilotHighAverageLatency` (warning);
  - `CareerPilotBackendTelemetryMissing` (info).
- **Rejected input:**
  - unknown alerts, invalid states, malformed timestamps, and unknown fields;
  - multi-line or over-long text, and text that looks like a secret.
- **Collector first:** when several alerts are present, a Collector-down alert is investigated first (runbook section 5.4).
- **Missing telemetry:** classified as `needs-investigation` unless the evidence explicitly shows an expected cause, such as OTLP export disabled or the backend not running.
- **Root cause:** stays `unknown` unless the evidence establishes it. It is never inferred from an alert name.
- **Resolution:** an incident is reported `resolved` only when the evidence includes complete recovery verification.
- **Incident report:** follows the runbook's incident template:
  - alert, severity, classification, and status;
  - UTC timeline;
  - evidence summary, root cause, and actions taken;
  - verification status and follow-ups.

  Every report is marked as requiring developer review.

Usage, from the repository root:

```powershell
python custom-agent/oncall_investigator.py EVIDENCE.json            # Markdown report
python custom-agent/oncall_investigator.py EVIDENCE.json --json     # JSON report
python custom-agent/oncall_investigator.py EVIDENCE.json --output report.md
```

Exit code `0` means a report was produced; `2` means the input was rejected. `--output` only creates a new file and never overwrites an existing one.

**Boundaries:**

- No live telemetry integration: it does not query Prometheus, Grafana, Loki, or Tempo.
- No automatic alert triggering: it runs only when a developer starts it.
- No remediation: it takes no actions and only reports.
- No network, database, Docker, or shell access, and no LLM calls. Nothing in the input is executed.
- Reports contain no request bodies, resume text, job descriptions, or secrets.

**Verification:**

- Historical: at commit `ae8a0ab`, 32 of 32 investigator tests and 38 of 38 custom-agent tests passed locally, and GitHub Actions CI run #27 passed all five jobs. The tests use synthetic input only.
- Current: the investigator now has 33 tests, part of the 90-test custom-agent suite that passed in the "Agent extension tests" job of CI run #32 (see the [CI workflow runs](https://github.com/robanc/CareerPilot/actions/workflows/ci.yml)).

### Prometheus Alert Adapter

[`custom-agent/prometheus_alert_adapter.py`](custom-agent/prometheus_alert_adapter.py) is a read-only, local-only adapter that takes a sanitized snapshot of the CareerPilot alerts Prometheus currently reports.

```powershell
python custom-agent/prometheus_alert_adapter.py --connect
```

- **Offline by default:** without `--connect` it makes no connection and exits with code `1`.
- **One fixed request:** with `--connect` it sends a single HTTP GET to `http://127.0.0.1:9090/api/v1/alerts`. It accepts no URL, query, or credentials, uses no proxies, refuses redirects, and enforces a 3-second timeout and a 256 KiB response limit.
- **Strict validation:** only the four CareerPilot alerts, with their documented severities, in state `pending` or `firing`, with timezone-aware `activeAt` timestamps. Anything unexpected rejects the whole response (exit code `2`).
- **Sanitized JSON output:** each alert carries only its name, severity, state, and UTC activation time. Annotations, other labels, and values are dropped. The snapshot is labelled `"source": "live-prometheus"` and `"synthetic": false`.
- **No conclusions:** an empty snapshot does not mean the system is healthy. The adapter does not diagnose root cause or verify recovery.
- **Separate from the investigator:** the snapshot is not passed to the On-Call Investigator, which accepts synthetic evidence only and rejects live snapshots.
- **No other access:** no database, Docker, shell, file writes, or remediation.

**Verification:** 21 of 21 adapter tests passed, using mocked HTTP responses only. Historically, the full custom-agent suite passed 59 of 59 at the time; the adapter tests are now part of the 90-test suite that passed in CI run #32. On October 26, 2026 (UTC), a live read-only query of the local Prometheus returned one firing `CareerPilotBackendTelemetryMissing` (info) alert. That alert was not diagnosed; a stopped local backend is a plausible explanation, not a confirmed cause.

The adapter is not an automated agent: it runs only when a developer passes `--connect`, it is not triggered by alerts, and it fixes nothing.

### On-Call Responder (Synthetic Only)

[`custom-agent/oncall_responder.py`](custom-agent/oncall_responder.py) demonstrates the full wake, repair, verify, and audit loop **only inside a disposable synthetic sandbox** created by [`custom-agent/synthetic_sandbox.py`](custom-agent/synthetic_sandbox.py). It does not fix live services.

```powershell
python custom-agent/oncall_responder.py --demo                      # create, inject a fault, respond, remove
python custom-agent/oncall_responder.py --sandbox DIR --once        # scan a sandbox's spool once
python custom-agent/oncall_responder.py --sandbox DIR --watch --interval 5 --max-cycles 10
```

- **Sandbox:** a marked temporary directory holding a synthetic service config with a fault switch, a known-good copy, an alert-event spool, and the audit log. Any directory without the marker, outside the system temp directory, inside the repository, or containing symlinks is refused.
- **Wake:** a new synthetic alert event (`"synthetic": true`, one of the four alerts) in the spool. `--once` scans once; `--watch` scans at most 100 times, 1 to 60 seconds apart.
- **One allowlisted repair:** for `CareerPilotHigh5xxRate` only, restore the sandbox's known-good config. The other three alerts are report-only.
- **Safeguards:**
  - the repair runs only if the 5xx condition is observed first;
  - the config is backed up and checked by SHA-256 before the repair;
  - each alert fingerprint is acted on at most once.
- **Verification and rollback:** the alert rule's thresholds (5xx ratio at most 0.05 over at least 10 synthetic requests). On failure, the original config is restored, checked by hash, and the incident stays open.
- **Audit and report:** a JSON Lines audit log of steps, hashes, counts, and outcomes, never contents, paths, or payloads. The incident report comes from the On-Call Investigator, with the repair recorded as `automated-synthetic-repair`.
- **No other access:** no network, database, Docker, shell, Render, or real CareerPilot code.

Exit code `0` means no incident was left open, `1` that one was, and `2` that the sandbox or arguments were refused.

**Verification:** in GitHub Actions CI run #32 (commit `54ea857`; see the [CI workflow runs](https://github.com/robanc/CareerPilot/actions/workflows/ci.yml)), the Linux custom-agent suite reported "Ran 90 tests" and "OK", with no skipped tests. That includes the 30 responder tests and their 3 symlink-refusal tests. Locally on Windows, 87 passed and the 3 symlink tests were skipped, because that account cannot create symlinks.

### Current Limitations

CareerPilot does not currently provide:

- A real (non-synthetic) alert that activates an on-call agent.
- On-Call Investigator or Responder integration with live telemetry or real alerts.
- Automated incident investigation based on local or production telemetry.
- An agent that diagnoses and fixes user-impacting failures in the real application.
- Automated remediation of any real service. The only automated repair is the synthetic sandbox repair.

Any future on-call agent should operate within explicit permission boundaries, maintain an audit trail, and require human approval before performing potentially destructive operations.

### Implementation References

- [Agent Extension Pack](docs/agent-extension-pack.md)
- [Agent Permissions](docs/permissions.md)
- [Security Reviewer](.agents/agents/security-reviewer.md)
- [Release Auditor](custom-agent/release_auditor.py)
- [On-Call Investigator](custom-agent/oncall_investigator.py)
- [On-Call Investigator Tests](custom-agent/tests/test_oncall_investigator.py)
- [Prometheus Alert Adapter](custom-agent/prometheus_alert_adapter.py)
- [Prometheus Alert Adapter Tests](custom-agent/tests/test_prometheus_alert_adapter.py)
- [On-Call Responder (synthetic only)](custom-agent/oncall_responder.py)
- [Synthetic Sandbox](custom-agent/synthetic_sandbox.py)
- [On-Call Responder Tests](custom-agent/tests/test_oncall_responder.py)
- [Incident Response Runbook](monitoring/INCIDENT_RESPONSE.md)
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

**Sample test data:** Use the [Fictional Sample Test Data](docs/sample-test-data.md) to test the workflows below without entering real personal information.

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



### 8. Start the Local Monitoring Stack

CareerPilot includes an independent monitoring stack for inspecting application metrics, logs, and traces.

From the repository root, run:

```powershell
docker compose -p careerpilot-monitoring -f monitoring/docker-compose.yml up -d
```

Open Grafana at http://127.0.0.1:3000 to explore the configured Prometheus, Loki, and Tempo data sources.

Backend OpenTelemetry export is enabled only when `CAREERPILOT_OTLP_ENABLED=true` is configured. Starting the monitoring stack alone does not enable backend telemetry export.

For detailed setup, verification commands, and example queries, see [Monitoring Documentation](monitoring/README.md).

### Known Limitations

- CareerPilot does not provide user authentication. Use synthetic or fictional data only, for tests, demonstrations, and the public demo.
- Do not inspect or alter existing development database records when reproducing or testing; backend tests use only the isolated test database.
- The Resume Library is available in local mode but disabled in public demonstration mode.
- Resume matching is deterministic and keyword-based; its score is not an assessment of candidate suitability.
- The Render public demo is on hold: an external PostgreSQL connection fails with a SCRAM channel-binding error whose root cause is unconfirmed (see [Deployment](#deployment)).
- Production deployment is not necessary to reproduce the local application or run the automated tests.

### Reproducibility References

- [Fictional Sample Test Data](docs/sample-test-data.md)
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

**Observability architecture:** The FastAPI backend emits HTTP metrics,
structured logs, and OpenTelemetry traces. The local monitoring stack
collects telemetry through the OpenTelemetry Collector and makes metrics
available in Prometheus, logs in Loki, and traces in Tempo. Grafana
provides a unified interface for investigating these signals.

See [Monitoring Documentation](monitoring/README.md) for setup and
verification instructions.

- **Frontend:** all API calls go through one module, `frontend/src/services/api.js`. In Docker, nginx
  serves the build and proxies `/api/` to the backend.
- **Backend:** routers, schemas, services, and models live under `backend/app/`.
  - `limits.py`: rate limits and the request body size cap (public demo only).
  - `readonly.py`: write blocking (public demo only).
  - `settings.py`: operating-mode selection.
- **Database:** PostgreSQL. Local mode creates missing tables on startup; the public demo never
  creates tables, and it refuses to start unless its database role is SELECT-only.


## Local setup

The complete local setup (prerequisites, the git-ignored `.env` file, `docker compose up --build --detach`, verification, and tests) is in [Reproducibility](#reproducibility). All ports are bound to 127.0.0.1 only.

To run the frontend dev server against the Docker backend instead of the nginx container:

    cd frontend && npm ci && VITE_API_URL=http://127.0.0.1:8002 npm run dev


## Security and data handling

- **Synthetic and fictional data only:** the MVP has no authentication. Tests, demonstrations,
  and the public demo must use synthetic or fictional data; the public demo shows only the
  fictional seed (`backend/scripts/seed_demo_data.py`). Do not inspect or alter existing
  development database records.
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
