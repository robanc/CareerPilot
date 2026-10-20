"""Tests for mcp-server/careerpilot_mcp.py (stdlib unittest; no network, no database).

Run from the repository root:
    python -m unittest discover -s mcp-server/tests
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "mcp-server" / "careerpilot_mcp.py"
sys.path.insert(0, str(SERVER.parent))

import careerpilot_mcp as mcp  # noqa: E402

SPEC_ENDPOINTS = {
    ("GET", "/health"), ("GET", "/config"), ("GET", "/version"),
    ("GET", "/applications"), ("POST", "/applications"),
    ("GET", "/applications/{id}"), ("PATCH", "/applications/{id}"),
    ("DELETE", "/applications/{id}"), ("GET", "/dashboard"), ("POST", "/resume/match"),
}


class Tools(unittest.TestCase):
    def test_list_api_endpoints_matches_the_contract(self):
        endpoints = mcp.call_tool("list_api_endpoints", {})["endpoints"]
        self.assertEqual({(e["method"], e["path"]) for e in endpoints}, SPEC_ENDPOINTS)
        self.assertTrue(all(e["summary"] for e in endpoints))

    def test_read_project_doc_allowlist_only(self):
        doc = mcp.call_tool("read_project_doc", {"name": "product-spec"})
        self.assertEqual(doc["path"], "product-spec.md")
        self.assertIn("CareerPilot", doc["text"])
        for name in [".env", "../.env", "backend/app/database.py", "openapi.yaml"]:
            with self.subTest(name=name):
                with self.assertRaises(mcp.ToolError):
                    mcp.call_tool("read_project_doc", {"name": name})

    def test_read_project_doc_rejects_extra_arguments(self):
        with self.assertRaises(mcp.ToolError):
            mcp.call_tool("read_project_doc", {"name": "agents", "path": ".env"})

    def test_match_resume_text_is_deterministic_and_bounded(self):
        args = {"resume_text": "Python and Docker", "job_description": "Python, Docker, AWS"}
        first = mcp.call_tool("match_resume_text", args)
        self.assertEqual(first, mcp.call_tool("match_resume_text", args))
        self.assertEqual(first["score"], 67)
        self.assertEqual(first["missing_keywords"], ["aws"])

    def test_match_resume_text_validation(self):
        for args in [
            {"resume_text": "", "job_description": "python"},
            {"resume_text": "   ", "job_description": "python"},
            {"resume_text": "a" * 20_001, "job_description": "python"},
            {"resume_text": "python"},
        ]:
            with self.subTest(args={k: len(v) for k, v in args.items()}):
                with self.assertRaises(mcp.ToolError):
                    mcp.call_tool("match_resume_text", args)
        mcp.call_tool("match_resume_text", {"resume_text": "a" * 20_000, "job_description": "python"})

    def test_server_never_imports_the_database_module(self):
        # backend.app.database loads .env and owns the engine; the MCP server
        # must stay away from both.
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); import careerpilot_mcp; "
             "print('backend.app.database' in sys.modules)", str(SERVER.parent)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.stdout.strip(), "False", result.stderr)

    def test_unknown_tool(self):
        with self.assertRaises(mcp.ToolError):
            mcp.call_tool("run_shell", {"command": "ls"})


class StdioProtocol(unittest.TestCase):
    """Drive the real server process over stdio, as an MCP client does."""

    def exchange(self, messages):
        stdin = "".join(json.dumps(m) + "\n" for m in messages)
        result = subprocess.run([sys.executable, str(SERVER)], input=stdin, capture_output=True,
                                text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_initialize_list_and_call(self):
        responses = self.exchange([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "match_resume_text",
                        "arguments": {"resume_text": "React", "job_description": "React and SQL"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "read_project_doc", "arguments": {"name": "nope"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
        ])
        self.assertEqual([r["id"] for r in responses], [1, 2, 3, 4, 5])  # notification: no reply
        self.assertEqual(responses[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(responses[0]["result"]["capabilities"], {"tools": {}})
        self.assertEqual(sorted(t["name"] for t in responses[1]["result"]["tools"]),
                         ["list_api_endpoints", "match_resume_text", "read_project_doc"])
        match = json.loads(responses[2]["result"]["content"][0]["text"])
        self.assertEqual((match["score"], match["missing_keywords"]), (50, ["sql"]))
        self.assertTrue(responses[3]["result"]["isError"])
        self.assertEqual(responses[4]["error"]["code"], -32601)

    def test_unknown_protocol_version_gets_the_latest_supported(self):
        response = self.exchange([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "1999-01-01"}}])[0]
        self.assertEqual(response["result"]["protocolVersion"], mcp.SUPPORTED_PROTOCOL_VERSIONS[0])

    def test_malformed_input_never_crashes_or_echoes(self):
        result = subprocess.run([sys.executable, str(SERVER)],
                                input='not json secret-marker-42\n{"jsonrpc":"1.0","id":9}\n',
                                capture_output=True, text=True, timeout=30)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r["error"]["code"] for r in responses], [-32700, -32600])
        self.assertNotIn("secret-marker-42", result.stdout + result.stderr)

    def test_resume_text_is_never_written_to_stderr(self):
        result = subprocess.run(
            [sys.executable, str(SERVER)],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "match_resume_text",
                                         "arguments": {"resume_text": "private-resume-marker python",
                                                       "job_description": "python"}}}) + "\n",
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("private-resume-marker", result.stdout)


if __name__ == "__main__":
    unittest.main()
