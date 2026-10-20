"""Tests for custom-agent/release_auditor.py (stdlib unittest; no network, no database).

Run from the repository root:
    python -m unittest discover -s custom-agent/tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "custom-agent" / "release_auditor.py"
sys.path.insert(0, str(AGENT.parent))

import release_auditor as ra  # noqa: E402


class FakeClient:
    """Stands in for the MCP server to exercise failure paths."""

    def __init__(self, tools, results):
        self.tools, self.results, self.calls = tools, results, []

    def request(self, method, params=None):
        if method == "initialize":
            return {"serverInfo": {"name": "fake", "version": "0"}}
        if method == "tools/list":
            return {"tools": [{"name": t} for t in self.tools]}
        self.calls.append(params["name"])
        return self.results(params["name"], params["arguments"])

    def notify(self, method):
        pass


def text_result(payload, is_error=False):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class EndToEnd(unittest.TestCase):
    def run_agent(self, *args):
        return subprocess.run([sys.executable, str(AGENT), *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=60, cwd=str(ROOT))

    def test_passes_against_the_real_server_and_writes_an_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            result = self.run_agent("--json", "--audit-log", str(log))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["passed"])
            self.assertEqual({c["check"] for c in report["checks"]},
                             {"contract", "match-determinism", "match-validation",
                              "deployment-gate", "permissions-doc", "audit-privacy"})
            lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 6)
            self.assertEqual([e["seq"] for e in lines], list(range(1, 7)))
            self.assertEqual(lines, report["audit"])

    def test_audit_log_never_contains_submitted_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            self.run_agent("--audit-log", str(log))
            content = log.read_text(encoding="utf-8")
        for value in ra.SAMPLE.values():
            self.assertNotIn(value, content)
        self.assertIn("chars>", content)

    def test_text_report(self):
        result = self.run_agent()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT: PASS", result.stdout)


class FailurePaths(unittest.TestCase):
    def test_missing_endpoint_and_safety_marker_fail(self):
        def results(name, arguments):
            if name == "list_api_endpoints":
                return text_result({"endpoints": [{"method": "GET", "path": "/health", "summary": "x"}]})
            if name == "match_resume_text":
                if not arguments["resume_text"]:
                    return text_result("resume_text must be non-empty text.", is_error=True)
                return text_result({"score": 50, "matched_keywords": [], "missing_keywords": [], "suggestions": []})
            if arguments["name"] == "deployment-render":
                return text_result({"text": "ready to ship"})
            return text_result("missing", is_error=True)

        tools = ["list_api_endpoints", "match_resume_text", "read_project_doc"]
        auditor = ra.ReleaseAuditor(FakeClient(tools, results), ra.AuditLog())
        auditor.connect()
        outcome = {c["check"]: c["passed"] for c in auditor.run()}
        self.assertFalse(outcome["contract"])
        self.assertFalse(outcome["deployment-gate"])
        self.assertFalse(outcome["permissions-doc"])
        self.assertTrue(outcome["match-validation"])

    def test_refuses_tools_the_server_does_not_offer(self):
        auditor = ra.ReleaseAuditor(FakeClient(["list_api_endpoints"], lambda n, a: None), ra.AuditLog())
        auditor.connect()
        with self.assertRaises(ra.ProtocolError):
            auditor.call("match_resume_text", ra.SAMPLE)

    def test_accepting_empty_input_fails_validation(self):
        def results(name, arguments):
            if name == "list_api_endpoints":
                return text_result({"endpoints": []})
            if name == "match_resume_text":
                return text_result({"score": 0, "matched_keywords": [], "missing_keywords": [], "suggestions": []})
            return text_result({"text": "NOT SAFE TO DEPLOY"})

        auditor = ra.ReleaseAuditor(
            FakeClient(["list_api_endpoints", "match_resume_text", "read_project_doc"], results), ra.AuditLog())
        auditor.connect()
        outcome = {c["check"]: c["passed"] for c in auditor.run()}
        self.assertFalse(outcome["match-validation"])


if __name__ == "__main__":
    unittest.main()
