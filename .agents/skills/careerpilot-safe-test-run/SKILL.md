---
name: careerpilot-safe-test-run
description: Run and report the CareerPilot backend test suite safely against the isolated PostgreSQL test container (127.0.0.1:5433) through ops/test-backend.ps1, with read-only preflight checks, explicit approval, and an accurate report. Use when asked to run, verify, or re-run backend tests.
---

# CareerPilot safe backend test run

Backend tests drop and recreate tables. This procedure keeps every run
inside the disposable `careerpilot_test` database on 127.0.0.1:5433 and
never touches the development database (5432), containers, or `.env`.

## Rules

- Get the developer's explicit approval for the run itself. The guardrail
  hook (`agent-hooks/guard.py`) asks for it automatically.
- Never start, stop, recreate, or remove containers. Never use `docker
  compose down -v`.
- Never read `.env`. Never run plain `pytest` against `backend/`: conftest
  refuses any endpoint other than 127.0.0.1:5433, and the runner sets the
  test environment.
- Never run SQL, seed data, commit, push, or deploy as part of a test run.

## Procedure

1. **Read-only preflight** (all must hold; otherwise stop and report):

   ```powershell
   docker inspect careerpilot-test-db-test-1 --format '{{.State.Status}} {{.State.Health.Status}} {{.Id}}'
   (Get-Command python).Source    # must be backend\.venv\Scripts\python.exe
   ```

   - **Container:** expect `running healthy`. If it is missing or stopped,
     ask the developer to start it themselves:
     `docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait`.
   - **Working directory:** run from the repository root.

2. **Run once, with approval:**

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1
   ```

   The runner refuses (exit 3) unless the container, the port, the mounts,
   and the cluster identity all match. It disables `.env` loading and
   neutralizes the connection and application variables.

3. **If the runner refuses with exit 3,** report its message verbatim. Do
   not work around it.

4. **Read-only post-check:** the same `docker inspect` must show the same
   container ID and start time.

## Report

State, without rounding or guessing:

- The exact command and its exit code.
- Totals from the pytest summary line (passed, failed, errors, skipped),
  plus every failing test ID and its assertion message.
- Warnings printed by the runner or by pytest.
- Confirmation that only `careerpilot_test` on 127.0.0.1:5433 was modified,
  and that the container ID is unchanged.
- Anything not verified.
