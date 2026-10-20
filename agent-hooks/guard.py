"""CareerPilot guardrail: a Claude Code PreToolUse hook (stdlib only).

Reads the hook payload (JSON) on stdin and applies the project's security
boundaries from AGENTS.md and CLAUDE.md:

- "deny": operations that are never allowed (reading secrets, recursive
  deletion, history-destroying git commands, printing .env through
  docker compose config, skipping git hooks).
- "ask": operations that need the developer's explicit approval (commits
  and pushes, Docker container and volume changes, SQL, destructive
  database statements, backend test runs, seeding, deploy hooks, and
  changes to the project's safety controls, whether made with a file tool
  or from the shell). The developer then approves or rejects that call.
- No output: everything else goes through the normal permission flow.

A payload that cannot be parsed, or an internal error, is denied (fail
closed). Each decision carries a reason that names the rule, so a rejected
call explains itself. Only the decision and reason are printed; command
text is never logged.

Usage (configured in .claude/settings.json):
    python agent-hooks/guard.py < payload.json
"""

import json
import re
import sys

SHELL_TOOLS = {"Bash", "PowerShell"}
FILE_TOOLS = {"Read", "Edit", "Write", "NotebookEdit"}
SEARCH_TOOLS = {"Grep", "Glob"}

# --- secret files ------------------------------------------------------------

SECRET_BASENAME = re.compile(
    r"^(\.env(\..+)?|.+\.(pem|key|p12|pfx)|id_(rsa|ed25519|ecdsa|dsa)(\.pub)?|\.pgpass|\.netrc)$",
    re.IGNORECASE,
)
ALLOWED_SECRET_LIKE = {".env.example"}

# ".env" or ".env.<suffix>" as a path token inside a command.
ENV_TOKEN = re.compile(
    r"(?:^|[\s\"'=/\\:(<])\.env(?:\.(?P<suffix>[\w.-]+))?(?=$|[\s\"';|&)>,])",
    re.IGNORECASE,
)

# --- shell command rules -------------------------------------------------------
# Each rule: (decision, compiled regex, reason). Checked in order; the first
# deny wins over any ask.

def _rx(pattern):
    return re.compile(pattern, re.IGNORECASE)


DENY_RULES = [
    (
        _rx(r"\brm\s+(-[a-z]*r[a-z]*|--recursive)\b|\brm\s+.*\s(-[a-z]*r[a-z]*|--recursive)\b"),
        "Recursive deletion (rm -r) is never allowed (AGENTS.md: no destructive operations).",
    ),
    (
        _rx(r"\bremove-item\b.*-recurse\b|\b(rmdir|rd)\s+/s\b|\bdel\s+/s\b"),
        "Recursive deletion (Remove-Item -Recurse, rmdir /s, del /s) is never allowed.",
    ),
    (
        _rx(r"\bgit\s+push\b.*(\s--force(-with-lease)?\b|\s-f\b|\s\+\S)"),
        "Force pushes are never allowed (CLAUDE.md, AGENTS.md: no destructive git commands).",
    ),
    (
        _rx(r"\bgit\s+reset\s+.*--hard\b|\bgit\s+reset\s+--hard\b"),
        "git reset --hard discards work and is never allowed.",
    ),
    (
        _rx(r"\bgit\s+clean\b"),
        "git clean deletes untracked files (including local Stage B files) and is never allowed.",
    ),
    (
        _rx(r"\bgit\s+(commit|push|merge|rebase)\b.*\s--no-verify\b|\bgit\s+commit\b.*\s-n\b"),
        "Skipping git hooks (--no-verify) is never allowed.",
    ),
]

ASK_RULES = [
    (
        _rx(r"\bgit\s+(commit|push|merge|rebase|tag|cherry-pick|revert|am)\b"),
        "Commits, pushes, merges, and history changes need the developer's explicit approval.",
    ),
    (
        _rx(r"\bgit\s+(restore|checkout\s+(.*\s)?--)\b|\bgit\s+branch\s+-d\b|\bgit\s+stash\s+(drop|clear)\b"),
        "Discarding local changes or deleting branches needs explicit approval.",
    ),
    (
        _rx(r"\bdocker(\s+compose|-compose)\b.*\s(up|down|start|stop|restart|rm|kill|run|create|exec|pull|build|cp|pause|unpause|scale)\b"),
        "Starting, stopping, recreating, or entering containers needs explicit approval.",
    ),
    (
        _rx(r"\bdocker\s+(container\s+)?(rm|rmi|stop|kill|start|restart|run|create|exec|cp|update|rename|pause|unpause|commit|volume|network|system|builder|image\s+(rm|prune))\b"),
        "Docker container, volume, network, or image changes need explicit approval.",
    ),
    (
        _rx(r"\bpsql\b|\bpg_dump\b|\bpg_restore\b|\bdropdb\b|\bcreatedb\b"),
        "Running SQL or database tools needs explicit approval (CLAUDE.md: database safety).",
    ),
    (
        _rx(r"\b(drop\s+(database|schema|table|role|user|owned|view|index|sequence)|truncate\s+(table\s+)?\w+|delete\s+from|drop_all)\b"),
        "Destructive database statements need explicit approval and must never target the development database.",
    ),
    (
        _rx(r"test-backend\.ps1|\bpytest\b[^|;&]*backend"),
        "Backend test runs touch the isolated test database and need explicit approval; use ops/test-backend.ps1.",
    ),
    (
        _rx(r"seed_demo_data\b.*--apply\b"),
        "Writing the fictional seed needs explicit approval.",
    ),
    (
        _rx(r"api\.render\.com|\brender\s+(deploy|services|psql|ssh|blueprint)|\bgh\s+(pr\s+merge|workflow\s+run|release)\b"),
        "Deployments and release actions need explicit approval (AGENTS.md: no unreviewed deployment).",
    ),
]

COMPOSE_CONFIG = _rx(r"\bdocker(\s+compose|-compose)\b.*\sconfig\b")
COMPOSE_CONFIG_SAFE = _rx(r"\s(--quiet|-q|--hash|--services|--volumes|--profiles)\b")

# Changes to these files change a safety control and need explicit approval.
PROTECTED_FILES = {
    "backend/tests/conftest.py",
    "backend/tests/db_safety.py",
    "ops/test-backend.ps1",
    "agent-hooks/guard.py",
    ".claude/settings.json",
    ".github/workflows/deploy.yml",
    "docker-compose.test.yml",
    "backend/tests/postgres/pg_hba.conf",
}

# Shell operations that write files. Redirects to the null device are not
# writes and are removed before this check.
SHELL_WRITE = _rx(
    r">|\bsed\s+(-[a-z]*i|--in-place)|\btee\b|\b(set|add)-content\b|\bout-file\b"
    r"|\b(copy|move|rename)-item\b|\b(cp|mv|truncate|install|dd)\b|\bopen\s*\([^)]*,\s*[\"'][wax]"
    r"|\bwrite_(text|bytes)\b|\.write\s*\("
)
NULL_REDIRECT = _rx(r"\d?>>?\s*(/dev/null|\$null|nul)\b|\d>&\d")


def decision(kind, reason):
    return {"decision": kind, "reason": reason}


def is_secret_path(path):
    if not path:
        return False
    base = re.split(r"[\\/]", str(path).rstrip("\\/"))[-1]
    if base.lower() in ALLOWED_SECRET_LIKE:
        return False
    return bool(SECRET_BASENAME.match(base))


def command_touches_env(command):
    for match in ENV_TOKEN.finditer(command):
        if (match.group("suffix") or "").lower() != "example":
            return True
    return False


def protected_file(path):
    """The protected repository file this path refers to, if any.

    Matched by path suffix, case-insensitively, so it works whether the
    path is relative, absolute, Windows-style (C:\\...), or Git-Bash-style
    (/c/...), and whatever CLAUDE_PROJECT_DIR looks like.
    """
    normalized = "/" + str(path).replace("\\", "/").lower()
    for name in PROTECTED_FILES:
        if normalized.endswith("/" + name.lower()):
            return name
    return None


def shell_writes_protected_file(command):
    """A protected file named in a command that also writes, if any."""
    lowered = command.replace("\\", "/").lower()
    named = [name for name in sorted(PROTECTED_FILES) if name.lower() in lowered]
    if named and SHELL_WRITE.search(NULL_REDIRECT.sub(" ", command)):
        return named[0]
    return None


def check_command(command):
    if command_touches_env(command):
        return decision("deny", "Access to .env files is never allowed (CLAUDE.md: secrets).")
    if COMPOSE_CONFIG.search(command) and not COMPOSE_CONFIG_SAFE.search(command):
        return decision(
            "deny",
            "docker compose config prints .env values; use --quiet (CLAUDE.md: secrets).",
        )
    for pattern, reason in DENY_RULES:
        if pattern.search(command):
            return decision("deny", reason)
    protected = shell_writes_protected_file(command)
    if protected:
        return decision(
            "ask",
            f"This shell command may change {protected}, a safety control; that needs explicit approval.",
        )
    for pattern, reason in ASK_RULES:
        if pattern.search(command):
            return decision("ask", reason)
    return None


def evaluate(payload):
    """Return a decision dict, or None for no opinion."""
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return decision("deny", "Malformed tool input; refusing (fail closed).")

    if tool in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return decision("deny", "Shell call without a command string; refusing (fail closed).")
        return check_command(command)

    if tool in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if is_secret_path(path):
            return decision("deny", "Secret files (.env, keys, credentials) are never read or written.")
        protected = protected_file(path) if tool != "Read" else None
        if protected:
            return decision(
                "ask",
                f"{protected} is a safety control; changing it needs explicit approval.",
            )
        return None

    if tool in SEARCH_TOOLS:
        for key in ("path", "glob", "pattern"):
            value = tool_input.get(key)
            if isinstance(value, str) and (is_secret_path(value) or command_touches_env(value)):
                return decision("deny", "Searching secret files (.env, keys) is never allowed.")
        return None

    return None


def main():
    try:
        payload = json.loads(sys.stdin.read() or "")
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
    except Exception:
        payload = None
        result = decision("deny", "Guard could not parse the hook payload; refusing (fail closed).")
    if payload is not None:
        try:
            result = evaluate(payload)
        except Exception as exc:
            result = decision(
                "deny",
                f"Guard internal error ({type(exc).__name__}); refusing (fail closed).",
            )

    if result is None:
        return 0
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": result["decision"],
                "permissionDecisionReason": "CareerPilot guard: " + result["reason"],
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
