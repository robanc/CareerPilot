"""CareerPilot release auditor: a small, auditable custom agent.

A deterministic agent (no LLM): it connects to the CareerPilot MCP server
(mcp-server/careerpilot_mcp.py) as an MCP client, discovers its tools, and
runs a fixed plan of release-readiness checks using ONLY those tools. It has
no shell, file, network, or database access of its own.

Every tool call is written to an audit log (JSON Lines): sequence number,
UTC time, tool, argument *names and sizes* (never their content), outcome,
and duration. Resume text and document contents never reach the log.

Checks (from product-spec.md acceptance criteria and the release rules):
  contract          every MVP endpoint is in the API contract
  match-determinism identical inputs give identical results, score 0-100
  match-validation  empty input is rejected
  deployment-gate   the deployment guide still says NOT SAFE TO DEPLOY
  permissions-doc   docs/permissions.md exists
  audit-privacy     the audit log holds no submitted text

Usage, from the repository root:
    python custom-agent/release_auditor.py [--audit-log PATH] [--json]
Exit code 0 when every check passes, 1 otherwise, 2 on a protocol error.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp-server" / "careerpilot_mcp.py"

REQUIRED_ENDPOINTS = {
    ("GET", "/health"), ("GET", "/applications"), ("POST", "/applications"),
    ("GET", "/applications/{id}"), ("PATCH", "/applications/{id}"),
    ("DELETE", "/applications/{id}"), ("GET", "/dashboard"), ("POST", "/resume/match"),
    ("GET", "/config"), ("GET", "/version"),
}
SAMPLE = {
    "resume_text": "Fictional resume: Python, FastAPI, PostgreSQL, Docker.",
    "job_description": "Fictional posting: Python, FastAPI, AWS, Docker, React.",
}


class ProtocolError(RuntimeError):
    pass


class AuditLog:
    """Append-only record of tool calls. Stores sizes, never content."""

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.entries = []

    def record(self, tool, arguments, ok, duration_ms):
        entry = {
            "seq": len(self.entries) + 1,
            "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "tool": tool,
            "arguments": {k: (f"<{len(v)} chars>" if isinstance(v, str) else type(v).__name__)
                          for k, v in sorted(arguments.items())},
            "ok": ok,
            "duration_ms": round(duration_ms, 1),
        }
        self.entries.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")


class McpClient:
    """Minimal MCP stdio client for one server process."""

    def __init__(self, command):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self.next_id = 1

    def request(self, method, params=None):
        msg_id = self.next_id
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
        line = self.process.stdout.readline()
        if not line:
            raise ProtocolError(f"server closed the connection during {method}")
        response = json.loads(line)
        if response.get("id") != msg_id:
            raise ProtocolError(f"unexpected response id for {method}")
        if "error" in response:
            raise ProtocolError(f"{method} failed: {response['error'].get('message')}")
        return response["result"]

    def notify(self, method):
        self._send({"jsonrpc": "2.0", "method": method})

    def _send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def close(self):
        if self.process.stdin:
            self.process.stdin.close()
        self.process.wait(timeout=10)


class ReleaseAuditor:
    def __init__(self, client, audit):
        self.client = client
        self.audit = audit
        self.tools = set()

    def connect(self):
        info = self.client.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "careerpilot-release-auditor", "version": "1.0.0"}})
        self.client.notify("notifications/initialized")
        self.tools = {tool["name"] for tool in self.client.request("tools/list")["tools"]}
        return info["serverInfo"]

    def call(self, tool, arguments):
        """Call one MCP tool; returns (ok, parsed payload or error text)."""
        if tool not in self.tools:
            raise ProtocolError(f"tool {tool!r} is not offered by the server")
        started = time.perf_counter()
        result = self.client.request("tools/call", {"name": tool, "arguments": arguments})
        ok = not result.get("isError", False)
        self.audit.record(tool, arguments, ok, (time.perf_counter() - started) * 1000)
        text = result["content"][0]["text"]
        return ok, (json.loads(text) if ok else text)

    def run(self):
        checks = []

        def check(name, passed, detail):
            checks.append({"check": name, "passed": bool(passed), "detail": detail})

        ok, payload = self.call("list_api_endpoints", {})
        found = {(e["method"], e["path"]) for e in payload["endpoints"]} if ok else set()
        missing = sorted(f"{m} {p}" for m, p in REQUIRED_ENDPOINTS - found)
        check("contract", ok and not missing,
              "all MVP endpoints present" if ok and not missing else f"missing: {', '.join(missing) or 'contract unreadable'}")

        first_ok, first = self.call("match_resume_text", SAMPLE)
        second_ok, second = self.call("match_resume_text", SAMPLE)
        deterministic = first_ok and second_ok and first == second and 0 <= first["score"] <= 100
        check("match-determinism", deterministic,
              f"score {first['score']} twice" if deterministic else "results differ or call failed")

        empty_ok, _ = self.call("match_resume_text", {"resume_text": "", "job_description": "Python"})
        check("match-validation", not empty_ok, "empty resume rejected" if not empty_ok else "empty resume accepted")

        doc_ok, doc = self.call("read_project_doc", {"name": "deployment-render"})
        gate = doc_ok and "NOT SAFE TO DEPLOY" in doc["text"]
        check("deployment-gate", gate,
              "guide still marks public_demo NOT SAFE TO DEPLOY" if gate else "safety marker missing")

        perm_ok, _ = self.call("read_project_doc", {"name": "permissions"})
        check("permissions-doc", perm_ok, "docs/permissions.md present" if perm_ok else "docs/permissions.md missing")

        log_text = json.dumps(self.audit.entries)
        leaked = any(value in log_text for value in SAMPLE.values())
        check("audit-privacy", not leaked, f"{len(self.audit.entries)} calls logged, no content"
              if not leaked else "submitted text found in audit log")
        return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description="CareerPilot release auditor (MCP client).")
    parser.add_argument("--audit-log", help="Append the JSON Lines audit log to this file.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = parser.parse_args(argv)

    audit = AuditLog(args.audit_log)
    client = McpClient([sys.executable, str(SERVER)])
    try:
        auditor = ReleaseAuditor(client, audit)
        server = auditor.connect()
        checks = auditor.run()
    except (ProtocolError, json.JSONDecodeError, KeyError) as exc:
        print(f"release auditor: protocol error: {exc}", file=sys.stderr)
        return 2
    finally:
        client.close()

    passed = all(c["passed"] for c in checks)
    if args.json:
        print(json.dumps({"server": server, "passed": passed, "checks": checks,
                          "audit": audit.entries}, indent=2))
    else:
        print(f"CareerPilot release auditor -> {server['name']} {server['version']}")
        for c in checks:
            print(f"  {'PASS' if c['passed'] else 'FAIL'}  {c['check']:<18} {c['detail']}")
        print(f"  audit: {len(audit.entries)} tool calls"
              + (f", appended to {args.audit_log}" if args.audit_log else ""))
        print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
