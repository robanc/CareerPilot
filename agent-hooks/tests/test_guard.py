"""Tests for agent-hooks/guard.py (stdlib unittest; no network, no database).

Run from the repository root:
    python -m unittest discover -s agent-hooks/tests
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "agent-hooks" / "guard.py"
sys.path.insert(0, str(GUARD.parent))

import guard  # noqa: E402


def shell(command, tool="Bash"):
    return {"tool_name": tool, "tool_input": {"command": command}}


def file_call(tool, path):
    return {"tool_name": tool, "tool_input": {"file_path": path}}


def decided(payload):
    result = guard.evaluate(payload)
    return None if result is None else result["decision"]


class SecretsAreDenied(unittest.TestCase):
    def test_reading_env_files(self):
        for path in [".env", "C:/repo/.env", r"C:\repo\.env.production", "backend/.env.local"]:
            with self.subTest(path=path):
                self.assertEqual(decided(file_call("Read", path)), "deny")

    def test_writing_env_files(self):
        self.assertEqual(decided(file_call("Write", ".env")), "deny")
        self.assertEqual(decided(file_call("Edit", "deploy/.env")), "deny")

    def test_keys_and_credentials(self):
        for path in ["certs/server.pem", "id_rsa", "deploy/prod.key", "~/.pgpass"]:
            with self.subTest(path=path):
                self.assertEqual(decided(file_call("Read", path)), "deny")

    def test_env_example_is_allowed(self):
        self.assertIsNone(decided(file_call("Read", ".env.example")))
        self.assertIsNone(decided(shell("cat .env.example")))

    def test_shell_access_to_env(self):
        for command in [
            "cat .env",
            "type .env",
            "Get-Content .env",
            'grep POSTGRES "$PWD/.env"',
            "cp .env /tmp/x",
            "python -c \"open('.env').read()\"",
        ]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "deny")

    def test_powershell_tool_is_checked_too(self):
        self.assertEqual(decided(shell("Get-Content .\\.env", tool="PowerShell")), "deny")

    def test_search_tools_cannot_target_env(self):
        self.assertEqual(decided({"tool_name": "Grep", "tool_input": {"pattern": "x", "path": ".env"}}), "deny")
        self.assertEqual(decided({"tool_name": "Glob", "tool_input": {"pattern": "**/.env"}}), "deny")

    def test_compose_config_must_be_quiet(self):
        self.assertEqual(decided(shell("docker compose config")), "deny")
        self.assertIsNone(decided(shell("docker compose config --quiet")))
        self.assertIsNone(decided(shell("docker compose -p careerpilot-test -f docker-compose.test.yml config --hash db-test")))

    def test_dotenv_disabled_variable_is_not_a_false_positive(self):
        self.assertIsNone(decided(shell("PYTHON_DOTENV_DISABLED=1 python -c 'print(1)'")))


class DestructiveCommandsAreDenied(unittest.TestCase):
    def test_recursive_deletion(self):
        for command in ["rm -rf dist", "rm -r backend/tests/stage-b-staging", "rm -fR x", "rm dist -r",
                        "Remove-Item -Recurse -Force build", "rmdir /s /q build", "del /s *.tmp"]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "deny")

    def test_single_file_rm_is_not_denied(self):
        self.assertIsNone(decided(shell("rm -f /tmp/stageb-tools/req.log")))

    def test_history_destroying_git(self):
        for command in ["git push --force origin main", "git push -f", "git push origin +main",
                        "git push --force-with-lease", "git reset --hard HEAD~1", "git clean -fd",
                        "git commit --no-verify -m x"]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "deny")


class ApprovalRequired(unittest.TestCase):
    def test_commit_push_merge(self):
        for command in ["git commit -m 'msg'", "git push origin feature/x", "git merge main", "git rebase main"]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "ask")

    def test_docker_lifecycle(self):
        for command in [
            "docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait",
            "docker compose down -v",
            "docker compose -p careerpilot-test down",
            "docker rm -f careerpilot-db-1",
            "docker volume rm postgres_data",
            "docker exec careerpilot-test-db-test-1 psql -U x",
            "docker restart careerpilot-backend-1",
        ]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "ask")

    def test_read_only_docker_is_allowed(self):
        for command in ["docker ps -a", "docker inspect careerpilot-test-db-test-1", "docker compose ps",
                        "docker logs careerpilot-backend-1"]:
            with self.subTest(command=command):
                self.assertIsNone(decided(shell(command)))

    def test_sql_and_destructive_statements(self):
        for command in ["psql -h 127.0.0.1 -p 5433 -f 02_render_demo_role.sql",
                        "python -c \"engine.execute('DROP TABLE job_applications')\"",
                        "echo 'TRUNCATE job_applications'", "python -c 'Base.metadata.drop_all(e)'"]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "ask")

    def test_backend_tests_seed_and_deploy(self):
        for command in [
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\ops\\test-backend.ps1",
            "python -m pytest backend/tests -v",
            "python -m backend.scripts.seed_demo_data --expect-database careerpilot_demo --expect-host h --expect-user u --apply --confirm u@h/careerpilot_demo",
            "curl -X POST https://api.render.com/deploy/srv-123?key=abc",
            "gh pr merge 2",
        ]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "ask")

    def test_seed_dry_run_is_not_asked(self):
        self.assertIsNone(decided(shell(
            "python -m backend.scripts.seed_demo_data --expect-database careerpilot_demo --expect-host h --expect-user u")))

    def test_editing_safety_controls_asks(self):
        root = str(ROOT)
        os.environ["CLAUDE_PROJECT_DIR"] = root
        try:
            for path in [f"{root}/backend/tests/conftest.py", f"{root}\\ops\\test-backend.ps1",
                         "./.claude/settings.json", "agent-hooks/guard.py"]:
                with self.subTest(path=path):
                    self.assertEqual(decided(file_call("Edit", path)), "ask")
            self.assertIsNone(decided(file_call("Read", f"{root}/backend/tests/conftest.py")))
        finally:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)


class ShellWritesToSafetyControls(unittest.TestCase):
    def test_shell_writes_to_protected_files_ask(self):
        for command in [
            "sed -i 's/5433/5432/' backend/tests/conftest.py",
            "echo '' > agent-hooks/guard.py",
            "python - <<'EOF'\nopen('agent-hooks/guard.py', 'w').write('')\nEOF",
            "cp /tmp/x .claude/settings.json",
            "Set-Content -Path .github/workflows/deploy.yml -Value x",
            "printf x | tee backend/tests/db_safety.py",
        ]:
            with self.subTest(command=command):
                self.assertEqual(decided(shell(command)), "ask")

    def test_reading_protected_files_from_the_shell_is_fine(self):
        for command in [
            "cat backend/tests/conftest.py",
            "grep -n guard agent-hooks/guard.py 2>/dev/null",
            "python -m py_compile agent-hooks/guard.py 2>&1 | tail -1",
            "git diff -- .claude/settings.json",
        ]:
            with self.subTest(command=command):
                self.assertIsNone(decided(shell(command)))


class EverydayWorkIsUntouched(unittest.TestCase):
    def test_safe_commands(self):
        for command in ["git status --short", "git diff --stat", "git log --oneline -5", "npm run lint",
                        "npm test", "npm run build", "python -m unittest discover -s agent-hooks/tests",
                        "cat README.md", "ls docs"]:
            with self.subTest(command=command):
                self.assertIsNone(decided(shell(command)))

    def test_safe_file_tools(self):
        self.assertIsNone(decided(file_call("Read", "README.md")))
        self.assertIsNone(decided(file_call("Edit", "frontend/src/App.jsx")))

    def test_other_tools_are_ignored(self):
        self.assertIsNone(decided({"tool_name": "WebSearch", "tool_input": {"query": ".env"}}))


class FailsClosed(unittest.TestCase):
    def test_malformed_shell_input(self):
        self.assertEqual(decided({"tool_name": "Bash", "tool_input": {}}), "deny")
        self.assertEqual(decided({"tool_name": "Bash", "tool_input": "rm -rf /"}), "deny")


class HookProtocol(unittest.TestCase):
    """End to end through the real process, as Claude Code would call it."""

    def run_hook(self, stdin):
        return subprocess.run([sys.executable, str(GUARD)], input=stdin, capture_output=True,
                              text=True, timeout=30)

    def test_deny_is_reported_as_pretooluse_json(self):
        result = self.run_hook(json.dumps(shell("cat .env")))
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("CareerPilot guard", output["permissionDecisionReason"])

    def test_no_opinion_prints_nothing(self):
        result = self.run_hook(json.dumps(shell("git status")))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_internal_errors_are_denied_with_an_accurate_reason(self):
        code = ("import io, json, sys; sys.path.insert(0, sys.argv[1]); import guard; "
                "guard.evaluate = lambda payload: 1 / 0; "
                "sys.stdin = io.StringIO(json.dumps({'tool_name': 'Bash', 'tool_input': {'command': 'ls'}})); "
                "guard.main()")
        result = subprocess.run([sys.executable, "-c", code, str(GUARD.parent)],
                                capture_output=True, text=True, timeout=30)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("internal error (ZeroDivisionError)", output["permissionDecisionReason"])

    def test_unparseable_payload_is_denied(self):
        result = self.run_hook("not json")
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_reason_never_echoes_the_command(self):
        result = self.run_hook(json.dumps(shell("cat .env  # secret-marker-123")))
        self.assertNotIn("secret-marker-123", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
