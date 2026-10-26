# Agent extension pack

Status: **implemented and tested.** The original pack was tested locally on
2026-10-20 (53 unittest tests passed), and the "Agent extension tests" CI
job now runs the extension tests; the latest verified CI run is #30. The
on-call responder (added 2026-10-26) has so far been tested locally only.

The pack covers what `product-spec.md` (section 7, "Agent Extensions")
requires, at the locations `AGENTS.md` names. Every component uses only the
Python standard library and has no database access. The only network access
is the Prometheus alert adapter's opt-in, read-only GET to
`127.0.0.1:9090`.

| Extension | Location | What it does | Tests |
|---|---|---|---|
| Reusable skill | `.agents/skills/careerpilot-safe-test-run/SKILL.md` | A safe backend test run through `ops/test-backend.ps1`: read-only preflight, explicit approval, an accurate report | `.agents/tests` |
| Specialized subagent | `.agents/agents/security-reviewer.md` | A read-only security reviewer (tools: Read, Grep, Glob) that checks diffs against `AGENTS.md` and the project's protections | `.agents/tests` |
| Guardrail hook | `agent-hooks/guard.py`, wired in `.claude/settings.json` (PreToolUse) | **deny** secrets access, recursive deletion, force pushes, `reset --hard`, `git clean`, `--no-verify`, and unmasked `docker compose config`; **ask** before commits and pushes, Docker lifecycle, SQL, backend tests, seeding, deploys, and changes to safety-control files (also from the shell) | `agent-hooks/tests` (30) |
| Scoped MCP server | `mcp-server/careerpilot_mcp.py`, wired in `.mcp.json` | Three read-only tools over stdio: `list_api_endpoints`, `read_project_doc` (allowlist only, no paths), `match_resume_text` (the deterministic matcher, 20,000-character limits, nothing logged) | `mcp-server/tests` (11) |
| Custom agent | `custom-agent/release_auditor.py` | A deterministic, auditable release auditor (no LLM). It uses only the MCP tools, runs six release checks, and writes a JSON Lines audit log (argument sizes, never content) | `custom-agent/tests` (6) |
| On-call investigator | `custom-agent/oncall_investigator.py` | Turns one synthetic alert-evidence file into a runbook-style incident report. Read-only; takes no actions | `custom-agent/tests` |
| Prometheus alert adapter | `custom-agent/prometheus_alert_adapter.py` | With `--connect` only: one read-only GET to the local Prometheus alerts endpoint, printed as a sanitized `synthetic: false` snapshot | `custom-agent/tests` (mocked HTTP) |
| On-call responder | `custom-agent/oncall_responder.py`, `custom-agent/synthetic_sandbox.py` | **Synthetic only.** Wakes on a synthetic alert event in a disposable sandbox, applies one allowlisted, reversible repair for `CareerPilotHigh5xxRate`, verifies it against the alert thresholds, rolls back on failure, and writes a privacy-safe JSON Lines audit log. Never touches a real service | `custom-agent/tests` |
| Permissions | `docs/permissions.md` | Allowed, approval-required, and denied actions, and how each is enforced | — |

## Activation and behavior

- **Hook and deny rules:** Claude Code loads them from `.claude/settings.json`.
  In this session the hook took effect as soon as the file was written; it
  can be reviewed with `/hooks`.
- **Fail closed:** `onFailure: "block"` blocks a call if the guard crashes.
  The guard also denies a payload it cannot parse, or an internal error,
  and gives the reason.
- **MCP server:** Claude Code offers project MCP servers from `.mcp.json` for
  approval on first use.
- **Skill and subagent:** they follow the `AGENTS.md` locations (`.agents/`).
  Claude Code discovers skills and subagents under `.claude/`, so to use them
  there, ask Claude Code to follow the file.

## Verified live in this session

- The guard denied a shell command that named a `.env` file.
- It denied file-tool calls while `guard.py` was half-edited (fail closed).
- It asked for approval before `guard.py` was rewritten.
- Six real payloads were checked: three protected-file edits gave `ask`, a
  `.env` read gave `deny`, and a README edit and a conftest read gave no
  decision.

## Limitations

- **The guard uses pattern rules,** not a shell parser. It can be evaded by
  obfuscated commands, and it can ask about harmless ones. Real protection
  comes from it together with the permission rules, the code guards, and
  human review.
- **One bypass happened before a gap was closed.** Before shell writes to
  protected files were covered, `guard.py` was repaired through a Bash
  command that the hook did not treat as a file write. That gap is now
  closed (it is `ask`).
- **The custom agent has no LLM.** It is deterministic by design, so its
  checks are reproducible.
- **The on-call responder is synthetic-only.** It is woken by synthetic
  spool events, not by real Prometheus alerts (no Alertmanager is
  configured), and it repairs only a disposable sandbox, never the
  CareerPilot application or any real service. Real-service remediation
  still needs developer approval (`docs/permissions.md`).
- **Symlink-refusal tests need symlink support.** They skip on systems that
  cannot create symlinks, such as Windows without Developer Mode.
- **`Read(./.env.*)`** would also deny a future `.env.example`.
