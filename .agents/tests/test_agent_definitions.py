"""Static checks for the skill and subagent definitions, and for the wiring
that activates the guardrail hook and MCP server (stdlib unittest).

Run from the repository root:
    python -m unittest discover -s .agents/tests
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"
AGENTS = ROOT / ".agents" / "agents"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def frontmatter(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = FRONTMATTER.match(text)
    if not match:
        raise AssertionError(f"{path} has no frontmatter")
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, text[match.end():]


class Definitions(unittest.TestCase):
    def test_skill_definitions(self):
        skills = sorted(SKILLS.glob("*/SKILL.md"))
        self.assertTrue(skills, "no skills found")
        for path in skills:
            with self.subTest(skill=path.parent.name):
                fields, body = frontmatter(path)
                self.assertEqual(fields.get("name"), path.parent.name)
                self.assertGreater(len(fields.get("description", "")), 40)
                self.assertIn("ops\\test-backend.ps1", body)
                self.assertIn("approval", body)

    def test_subagent_definitions_are_read_only(self):
        agents = sorted(AGENTS.glob("*.md"))
        self.assertTrue(agents, "no subagents found")
        for path in agents:
            with self.subTest(agent=path.stem):
                fields, body = frontmatter(path)
                self.assertEqual(fields.get("name"), path.stem)
                self.assertTrue(fields.get("description"))
                tools = {t.strip() for t in fields.get("tools", "").split(",")}
                self.assertEqual(tools, {"Read", "Grep", "Glob"})
                self.assertIn("never edit", body.lower())

    def test_referenced_files_exist(self):
        for path in list(SKILLS.glob("*/SKILL.md")) + list(AGENTS.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for ref in re.findall(r"`((?:backend|ops|agent-hooks|mcp-server|custom-agent|docs|deploy)/[\w./-]+\.\w+)`", text):
                with self.subTest(file=path.name, ref=ref):
                    self.assertTrue((ROOT / ref).exists(), ref)


class Wiring(unittest.TestCase):
    def test_guard_hook_is_configured(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        entries = settings["hooks"]["PreToolUse"]
        commands = [h["command"] for e in entries for h in e["hooks"] if h["type"] == "command"]
        self.assertTrue(any("agent-hooks/guard.py" in c for c in commands))
        matcher = next(e["matcher"] for e in entries
                       if any("guard.py" in h["command"] for h in e["hooks"]))
        for tool in ["Bash", "PowerShell", "Read", "Edit", "Write", "Grep", "Glob"]:
            self.assertIn(tool, matcher.split("|"))
        hook = next(h for e in entries for h in e["hooks"] if "guard.py" in h["command"])
        self.assertEqual(hook.get("onFailure"), "block", "a crashed guard must not let calls through")

    def test_env_reads_are_denied_by_permission_rules(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        deny = settings["permissions"]["deny"]
        self.assertIn("Read(./.env)", deny)
        self.assertIn("Read(./.env.*)", deny)

    def test_mcp_server_is_configured(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["careerpilot"]
        self.assertEqual(server["type"], "stdio")
        self.assertIn("mcp-server/careerpilot_mcp.py", " ".join(server["args"]))


if __name__ == "__main__":
    unittest.main()
