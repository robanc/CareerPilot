# CareerPilot — AI Coding Agent Instructions

## Project Overview

CareerPilot is an AI-assisted job application tracking and career preparation platform developed for the AI Dev Tools Zoomcamp 2026 capstone.

The application helps job seekers manage applications, track interviews, view application statistics, and compare resume text with job descriptions.

Read `product-spec.md` before implementing features.

## Source of Truth

Use the following documents in order:

1. `product-spec.md` — product requirements and acceptance criteria.
2. `openapi.yaml` — frontend/backend API contract.
3. `AGENTS.md` — engineering workflow, constraints, and security rules.
4. `docs/` — architecture, decisions, testing, and operational documentation.

When requirements conflict, report the conflict rather than silently changing the specification.

## Technology Stack

- Frontend: React, Vite, JavaScript
- Backend: Python 3.12+, FastAPI, Pydantic
- Database: PostgreSQL and SQLAlchemy
- API contract: OpenAPI 3.x
- Testing: Pytest, Vitest, integration tests
- Containerization: Docker and Docker Compose
- CI/CD: GitHub Actions
- Deployment: Cloud-hosted demonstration environment

## Repository Structure

    frontend/             React application
    backend/              FastAPI application and database
    docs/                 Architecture, decisions, AI workflow, demo
    security/             Security scans and audit evidence
    ops/                  Operational diagnosis and runbooks
    agent-capabilities/   Reusable agent workflows and specialists
    agent-hooks/          Agent guardrails
    mcp-server/           Scoped MCP tools
    custom-agent/         Auditable custom agent
    .github/workflows/    CI/CD pipelines

## Development Workflow

For every feature:

1. Read the relevant product specification.
2. Identify or update the OpenAPI contract.
3. Break the work into small, reviewable tasks.
4. Implement the smallest complete change.
5. Add or update relevant tests.
6. Run verification commands.
7. Review the Git diff.
8. Document important decisions and test results.

Do not claim a feature is complete unless its acceptance criteria have been verified.

## API Contract Rules

- Treat `openapi.yaml` as the source of truth for HTTP endpoints.
- Keep request and response schemas consistent with the contract.
- Use Pydantic for request validation.
- Centralize frontend API calls in `frontend/src/services/api.js`.
- Do not make direct backend requests from UI components.
- Document changes to status codes, error responses, and validation behavior.

## Backend Rules

- Separate routes, schemas, services, and persistence logic.
- Use SQLAlchemy for database access.
- Keep business logic out of route handlers when practical.
- Validate required fields and supported application statuses.
- Use UTC-aware timestamps for stored dates and events.
- Make resume matching deterministic and testable.
- Do not persist or log resume text submitted for matching.

## Frontend Rules

- Use React functional components.
- Keep API communication in the service layer.
- Build accessible forms with labels and validation feedback.
- Provide loading, empty, and error states.
- Add tests for core application workflows.
- Avoid unnecessary frontend dependencies.

## Testing Requirements

Tests should cover:

- Application creation, retrieval, updating, and deletion.
- Required-field validation.
- Application status filtering and search.
- Dashboard counts and upcoming interviews.
- Resume matching and invalid inputs.
- Database persistence.
- API contract consistency.
- Frontend service-layer behavior.
- End-to-end workflows across components.

Run relevant tests before committing.

## Agent Skills and Subagents

Project-specific discoverable skills belong under:

    .agents/skills/<skill-name>/SKILL.md

Specialized subagents belong under:

    .agents/agents/<agent-name>.md

Each skill and subagent definition should include `name` and `description` frontmatter.

Use a specialized reviewer in a separate context for API changes and security-sensitive work when supported by the coding assistant.

Agent extension documentation belongs under:

    docs/agent-extension-pack.md
    docs/permissions.md

## Security Boundaries

Agents must not:

- Read or expose secrets, API keys, passwords, or private keys.
- Commit `.env` files containing credentials.
- Log or persist resume content submitted for matching.
- Access unrelated files or services.
- Run destructive Git commands without approval.
- Modify cloud infrastructure without explicit approval.
- Deploy unreviewed code.
- Expose real job-search records through the public demo.

Use synthetic data for tests and demonstrations.

MCP tools should expose narrowly scoped capabilities rather than arbitrary shell or filesystem access.

Guardrails should reject protected operations safely and explain why they were rejected.

## AI-Assisted Development Evidence

For significant features, record:

- Task or prompt given to the coding assistant.
- Relevant context files supplied.
- Files changed.
- Manual review performed.
- Tests executed and their results.
- Any corrections or follow-up prompts.

Maintain this evidence in `docs/ai-development-log.md`.

## Definition of Done

A task is complete when:

1. Requirements and API contract are consistent.
2. Implementation is functional.
3. Relevant tests pass.
4. Security constraints are respected.
5. The Git diff has been reviewed.
6. Documentation is updated.
7. Remaining limitations are reported accurately.