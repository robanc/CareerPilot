# Agent permissions

What AI coding agents may do in this repository, and how each rule is
enforced. The policy comes from `AGENTS.md` ("Security Boundaries") and
`CLAUDE.md` ("Working rules"). Enforcement is layered:

1. **Claude Code permission rules** (`.claude/settings.json`, `permissions.deny`):
   hard denials evaluated by Claude Code itself.
2. **The guardrail hook** (`agent-hooks/guard.py`, a PreToolUse hook configured in
   `.claude/settings.json`). For every shell, file, and search tool call it
   returns one of three outcomes:
   - `deny` (never allowed);
   - `ask` (needs the developer's approval of that specific call);
   - no decision (the normal permission flow applies).

   Every decision carries a reason that names the rule.
3. **Fail-closed code guards**, which hold even if the agent layers above
   are bypassed:
   - `ops/test-backend.ps1` and the endpoint guard in `backend/tests/conftest.py`;
   - `backend/tests/db_safety.py`;
   - the seed script's target checks;
   - the `.sql.review` interlock;
   - the gates in `deploy.yml`.
4. **Human review:** every commit, push, merge, database change, and
   deployment is approved by the developer (`docs/ai-development-log.md`,
   "Human Oversight").

## Rules

| Area | Allowed without asking | Needs explicit approval (`ask`) | Never (`deny`) |
|---|---|---|---|
| Source files | Read and edit application code, tests, docs | Edits to safety controls: `backend/tests/conftest.py`, `backend/tests/db_safety.py`, `ops/test-backend.ps1`, `agent-hooks/guard.py`, `.claude/settings.json`, `.github/workflows/deploy.yml`, `docker-compose.test.yml`, the test `pg_hba.conf` | Reading, writing, or searching `.env`, `.env.*` (except `.env.example`), keys and credentials (`*.pem`, `*.key`, `id_*`, `.pgpass`, `.netrc`) |
| Shell | Linters, frontend tests and build, `git status`/`diff`/`log`, read-only `docker ps`/`inspect`/`logs`, the agent-extension unittest suites | — | Any command naming a `.env` file; `docker compose config` without `--quiet` (it prints `.env` values) |
| Deletion | Single named files | — | Recursive deletion: `rm -r`, `Remove-Item -Recurse`, `rmdir /s`, `del /s`; `git clean` |
| Git | Read-only commands | `commit`, `push`, `merge`, `rebase`, `tag`, `cherry-pick`, `revert`; discarding changes (`restore`, `checkout --`); deleting branches | Force pushes (`--force`, `-f`, `+ref`), `reset --hard`, `--no-verify` |
| Docker | `ps`, `inspect`, `logs` | `up`, `down` (including `-v`), `start`, `stop`, `restart`, `rm`, `run`, `exec`, volume, network, and image changes | — |
| Databases | — | `psql` and other database tools; destructive statements (`DROP`, `TRUNCATE`, `DELETE FROM`, `drop_all`) | Targeting the development database; backend tests reject any endpoint other than 127.0.0.1:5433 |
| Tests | Frontend tests; agent-extension tests | Backend tests (`ops/test-backend.ps1`, pytest on `backend/`) | — |
| Data | Fictional data only | Writing the fictional seed (`seed_demo_data --apply`) | Real personal data |
| Deployment | — | Render deploy hooks, `render` CLI, `gh pr merge`, `gh workflow run`, `gh release` | Deploying unreviewed code |

## MCP and custom agent scope

- **MCP server** (`mcp-server/careerpilot_mcp.py`): three read-only tools.
  - Endpoints from `openapi.yaml`.
  - One of six allowlisted documents, chosen by name; there is no path
    parameter.
  - The deterministic resume matcher.

  It has no shell, network, database, or write access, and never logs
  arguments.
- **Custom agent** (`custom-agent/release_auditor.py`): uses only the tools
  the MCP server offers. It refuses any other tool and records every call in
  an audit log, with argument sizes only.
- **On-call investigator** (`custom-agent/oncall_investigator.py`): reads one
  synthetic evidence file and writes a report. It takes no actions.
- **Prometheus alert adapter** (`custom-agent/prometheus_alert_adapter.py`):
  one read-only GET to the fixed local Prometheus alerts endpoint, and only
  with `--connect`.
- **On-call responder** (`custom-agent/oncall_responder.py`): the only
  component that changes anything without per-action approval, and only
  inside a disposable synthetic sandbox (`custom-agent/synthetic_sandbox.py`).
  - It refuses any directory that lacks the sandbox marker, is outside the
    system temp directory or inside the repository, or contains symlinks.
  - Its one allowlisted repair, for `CareerPilotHigh5xxRate` only, restores
    the sandbox's known-good config. The repair is backed up, verified, and
    rolled back if verification fails.
  - It records every step in a JSON Lines audit log (hashes and counts, never
    contents), and reports the repair as `automated-synthetic-repair`.
  - It has no network, database, Docker, or shell access.

## Synthetic sandbox repair versus real-service remediation

| | Synthetic sandbox repair | Real-service remediation |
|---|---|---|
| Target | A disposable temporary directory created by `synthetic_sandbox.py` | The CareerPilot application, its databases, containers, the monitoring stack, or Render |
| Who acts | `oncall_responder.py`, automatically | A developer, or an agent with explicit developer approval per action |
| Allowed actions | One allowlisted, reversible config restore | Whatever the developer approves (`monitoring/INCIDENT_RESPONSE.md`) |
| Approval | None per action; bounded by the allowlist and sandbox checks | **Always required** |
| Recorded as | `automated-synthetic-repair` | `approved-by-developer` |

No rule in this document lets the responder, or any agent, remediate a real
service without the developer's approval.

## Activation

- **Approve the hooks:** Claude Code reads `.claude/settings.json` at
  startup. Review and approve the hooks once through `/hooks`; that is
  Claude Code's own safety check for project hooks.
- **Approve the MCP server:** project MCP servers in `.mcp.json` must be
  approved when Claude Code first offers them.
- **Turn it off:** remove the entry from `.claude/settings.json`. That is
  itself a protected edit, so the guard asks for approval first.
