"""CareerPilot MCP server: narrowly scoped, read-only tools over stdio.

Implements the Model Context Protocol's JSON-RPC 2.0 stdio transport
(newline-delimited messages) with the standard library only.

Tools (and nothing else):
- list_api_endpoints: method, path, and summary of every operation in
  openapi.yaml, the project's API contract.
- read_project_doc: the text of one allowlisted project document. Names are
  an enum; there is no path parameter, so no other file can be read.
- match_resume_text: the backend's deterministic keyword matcher
  (backend/app/services/resume_matcher.py) on supplied text, with the same
  20,000-character limits as the API. Text is not stored or logged.

No shell, network, database, or write access. stdout carries only protocol
messages; nothing about tool arguments is logged.

Run: python mcp-server/careerpilot_mcp.py   (configured in .mcp.json)
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Pure function: imports only "re". Never touches the database or .env.
from backend.app.services.resume_matcher import match_resume  # noqa: E402

SERVER_INFO = {"name": "careerpilot", "version": "1.0.0"}
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_TEXT_LENGTH = 20_000  # backend/app/schemas.py RESUME_TEXT/JOB_DESCRIPTION limits
MAX_DOC_CHARS = 200_000

ALLOWED_DOCS = {
    "product-spec": "product-spec.md",
    "openapi": "openapi.yaml",
    "agents": "AGENTS.md",
    "deployment-render": "docs/deployment-render.md",
    "agent-extension-pack": "docs/agent-extension-pack.md",
    "permissions": "docs/permissions.md",
}

TOOLS = [
    {
        "name": "list_api_endpoints",
        "description": "List every HTTP operation in the CareerPilot API contract (openapi.yaml): method, path, summary.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "read_project_doc",
        "description": "Read one allowlisted CareerPilot project document by name.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": sorted(ALLOWED_DOCS)}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "match_resume_text",
        "description": (
            "Run CareerPilot's deterministic, keyword-based heuristic matcher on resume text "
            "and a job description (each 1-20,000 characters). Nothing is stored or logged."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "resume_text": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT_LENGTH},
                "job_description": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT_LENGTH},
            },
            "required": ["resume_text", "job_description"],
            "additionalProperties": False,
        },
    },
]

PATH_LINE = re.compile(r"^  (/\S*):\s*$")
METHOD_LINE = re.compile(r"^    (get|post|put|patch|delete|head|options):\s*$")
SUMMARY_LINE = re.compile(r"^      summary:\s*(.+?)\s*$")


class ToolError(Exception):
    """A tool-level failure, reported to the client as isError content."""


def list_api_endpoints():
    endpoints, path, current = [], None, None
    for line in (ROOT / "openapi.yaml").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(" ") and line.rstrip() != "paths:":
            path = None  # left the paths section
        if match := PATH_LINE.match(line):
            path, current = match.group(1), None
        elif path and (match := METHOD_LINE.match(line)):
            current = {"method": match.group(1).upper(), "path": path, "summary": ""}
            endpoints.append(current)
        elif current and (match := SUMMARY_LINE.match(line)):
            current["summary"] = match.group(1)
    return {"endpoints": endpoints}


def read_project_doc(name):
    if name not in ALLOWED_DOCS:
        raise ToolError(f"Unknown document; allowed: {', '.join(sorted(ALLOWED_DOCS))}.")
    path = ROOT / ALLOWED_DOCS[name]
    if not path.is_file():
        raise ToolError(f"Document {name!r} does not exist yet.")
    text = path.read_text(encoding="utf-8")
    return {"name": name, "path": ALLOWED_DOCS[name], "truncated": len(text) > MAX_DOC_CHARS,
            "text": text[:MAX_DOC_CHARS]}


def match_resume_text(resume_text, job_description):
    for field, value in (("resume_text", resume_text), ("job_description", job_description)):
        if not isinstance(value, str) or not value.strip():
            raise ToolError(f"{field} must be non-empty text.")
        if len(value) > MAX_TEXT_LENGTH:
            raise ToolError(f"{field} exceeds {MAX_TEXT_LENGTH} characters.")
    return match_resume(resume_text=resume_text, job_description=job_description)


def call_tool(name, arguments):
    if not isinstance(arguments, dict):
        raise ToolError("Tool arguments must be an object.")
    if name == "list_api_endpoints":
        if arguments:
            raise ToolError("list_api_endpoints takes no arguments.")
        return list_api_endpoints()
    if name == "read_project_doc":
        if set(arguments) != {"name"}:
            raise ToolError("read_project_doc takes exactly one argument: name.")
        return read_project_doc(arguments["name"])
    if name == "match_resume_text":
        if set(arguments) != {"resume_text", "job_description"}:
            raise ToolError("match_resume_text takes resume_text and job_description.")
        return match_resume_text(arguments["resume_text"], arguments["job_description"])
    raise ToolError(f"Unknown tool: {name}")


def handle(message):
    """Return a response dict, or None for notifications."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return error_response(None, -32600, "Invalid request")
    method, msg_id, params = message.get("method"), message.get("id"), message.get("params") or {}
    if "id" not in message:  # notification (e.g. notifications/initialized)
        return None
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
        return result_response(msg_id, {"protocolVersion": version, "capabilities": {"tools": {}},
                                        "serverInfo": SERVER_INFO})
    if method == "ping":
        return result_response(msg_id, {})
    if method == "tools/list":
        return result_response(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        try:
            payload = call_tool(params.get("name"), params.get("arguments") or {})
            return result_response(msg_id, {"content": [{"type": "text", "text": json.dumps(payload)}],
                                            "isError": False})
        except ToolError as exc:
            return result_response(msg_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return error_response(msg_id, -32601, f"Method not found: {method}")


def result_response(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def error_response(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def serve(stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = error_response(None, -32700, "Parse error")
        else:
            try:
                response = handle(message)
            except Exception:  # never crash the session; never echo inputs
                response = error_response(message.get("id") if isinstance(message, dict) else None,
                                          -32603, "Internal error")
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


if __name__ == "__main__":
    # MCP messages are UTF-8 regardless of the platform's console code page.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    serve()
