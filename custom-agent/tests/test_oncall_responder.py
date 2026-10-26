"""Tests for custom-agent/oncall_responder.py and synthetic_sandbox.py.

Stdlib unittest. Every test uses a disposable synthetic sandbox in the system
temp directory: no network, database, Docker, monitoring stack, or real
CareerPilot service. Run from the repository root:
    python -m unittest discover -s custom-agent/tests
"""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "custom-agent"
RESPONDER = AGENT_DIR / "oncall_responder.py"
SANDBOX_MODULE = AGENT_DIR / "synthetic_sandbox.py"
RULES = ROOT / "monitoring" / "alerts" / "careerpilot.rules.yml"
sys.path.insert(0, str(AGENT_DIR))

import oncall_investigator as oi  # noqa: E402
import oncall_responder as resp  # noqa: E402
import synthetic_sandbox as sb  # noqa: E402

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
STARTS = "2026-10-26T11:50:00Z"
FIVE_XX = "CareerPilotHigh5xxRate"


def clock():
    return NOW


def severity(name):
    return oi.ALERTS[name]["severity"]


class SandboxCase(unittest.TestCase):
    def setUp(self):
        self.root = sb.create_sandbox()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        if self.root.exists():
            sb.remove_sandbox(self.root)

    def responder(self):
        return resp.Responder(resp.Sandbox(self.root), clock)

    def event(self, name=FIVE_XX, **kwargs):
        return sb.write_alert_event(self.root, name, severity(name), STARTS, **kwargs)

    def config_bytes(self):
        return (self.root / sb.CONFIG_NAME).read_bytes()

    def audit(self):
        text = (self.root / sb.AUDIT_NAME).read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def steps(self):
        return [entry["step"] for entry in self.audit()]


class Wake(SandboxCase):
    def test_empty_spool_does_nothing(self):
        responder = self.responder()
        self.assertEqual(responder.run_cycle(), [])
        self.assertFalse((self.root / sb.AUDIT_NAME).exists())

    def test_new_event_wakes_exactly_one_cycle_and_is_not_reprocessed(self):
        sb.inject_fault(self.root)
        self.event()
        responder = self.responder()
        self.assertEqual(len(responder.run_cycle()), 1)
        self.assertEqual(responder.run_cycle(), [])
        self.assertEqual(self.steps().count("woke"), 1)

    def test_watch_is_bounded_and_wakes_on_an_event_that_arrives_later(self):
        sb.inject_fault(self.root)
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 1:
                self.event()

        results = self.responder().watch(max_cycles=3, interval=2, sleep=fake_sleep)
        self.assertEqual(sleeps, [2, 2])
        self.assertEqual([r["outcome"] for r in results], ["resolved"])

    def test_invalid_events_are_rejected_and_audited(self):
        spool = self.root / sb.SPOOL_NAME
        good = {"schema_version": 1, "synthetic": True, "source": sb.EVENT_SOURCE,
                "alertname": FIVE_XX, "severity": "warning", "state": "firing",
                "starts_at": STARTS, "fingerprint": "0123456789abcdef"}
        cases = {
            "unknown": {**good, "alertname": "CareerPilotDiskFull"},
            "not-synthetic": {**good, "synthetic": False},
            "live-source": {**good, "source": "live-prometheus"},
            "severity": {**good, "severity": "critical"},
            "state": {**good, "state": "resolved"},
            "naive-time": {**good, "starts_at": "2026-10-26T11:50:00"},
            "future": {**good, "starts_at": "2026-10-26T13:00:00Z"},
            "fingerprint": {**good, "fingerprint": "XYZ"},
            "extra-field": {**good, "request_body": "x"},
        }
        for label, event in cases.items():
            (spool / f"{label}.json").write_text(json.dumps(event), encoding="utf-8")
        (spool / "garbage.json").write_bytes(b"{not json")
        before = self.config_bytes()
        self.assertEqual(self.responder().run_cycle(), [])
        self.assertEqual(self.steps().count("event-rejected"), len(cases) + 1)
        self.assertEqual(self.config_bytes(), before)


class Success(SandboxCase):
    def test_fault_is_repaired_verified_reported_and_audited(self):
        sb.inject_fault(self.root)
        original = self.config_bytes()
        _, fp = self.event()
        [result] = self.responder().run_cycle()

        self.assertEqual(result["outcome"], "resolved")
        report = result["report"]
        self.assertEqual(report["status"], "resolved")
        self.assertEqual(report["verification"]["status"], "verified")
        self.assertEqual(report["actions_taken"]["recorded"][0]["approval"],
                         "automated-synthetic-repair")
        self.assertIn("Injected synthetic fault", report["root_cause"])
        self.assertTrue(report["synthetic"])

        self.assertEqual(json.loads(self.config_bytes())["fault_5xx"], False)
        backup = self.root / f"config-backup-{fp}.json"
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(self.steps(), ["woke", "condition-check", "backup-saved",
                                        "repair-applied", "verification", "reported"])
        applied = next(e for e in self.audit() if e["step"] == "repair-applied")
        self.assertEqual(applied["config_sha256_before"], resp.sha256(original))
        self.assertEqual(applied["config_sha256_after"], resp.sha256(self.config_bytes()))
        verification = next(e for e in self.audit() if e["step"] == "verification")
        self.assertEqual((verification["requests"], verification["errors_5xx"]), (20, 0))

    def test_no_repair_when_the_condition_is_not_observed(self):
        before = self.config_bytes()
        self.event()
        [result] = self.responder().run_cycle()
        self.assertEqual(result["outcome"], "condition-not-observed")
        self.assertEqual(result["report"]["status"], "open")
        self.assertEqual(self.config_bytes(), before)
        self.assertNotIn("repair-applied", self.steps())


class FailureAndRollback(SandboxCase):
    def test_failed_verification_rolls_back_to_the_exact_original(self):
        sb.inject_fault(self.root, persistent=True)
        original = self.config_bytes()
        self.event()
        [result] = self.responder().run_cycle()

        self.assertEqual(result["outcome"], "rolled-back")
        self.assertEqual(result["report"]["status"], "open")
        self.assertEqual(result["report"]["root_cause"], "unknown")
        self.assertEqual(self.config_bytes(), original)
        rolled = next(e for e in self.audit() if e["step"] == "rolled-back")
        self.assertEqual(rolled["outcome"], "restored")
        self.assertEqual(rolled["config_sha256_after"], resp.sha256(original))
        self.assertIn("verification", self.steps())
        self.assertTrue(any("verification" in item for item in result["report"]["follow_ups"]))

    def test_invalid_known_good_config_refuses_the_repair(self):
        sb.inject_fault(self.root)
        (self.root / sb.KNOWN_GOOD_NAME).write_text('{"fault_5xx": true}', encoding="utf-8")
        before = self.config_bytes()
        self.event()
        [result] = self.responder().run_cycle()
        self.assertEqual(result["outcome"], "repair-refused")
        self.assertEqual(self.config_bytes(), before)


class Allowlist(SandboxCase):
    def test_other_alerts_are_report_only(self):
        sb.inject_fault(self.root)
        before = self.config_bytes()
        for name in ("CareerPilotOtelCollectorDown", "CareerPilotHighAverageLatency",
                     "CareerPilotBackendTelemetryMissing"):
            self.event(name)
        results = self.responder().run_cycle()
        self.assertEqual(sorted(r["outcome"] for r in results), ["report-only"] * 3)
        self.assertTrue(all(r["report"]["status"] == "open" for r in results))
        self.assertEqual(self.config_bytes(), before)
        self.assertEqual(self.steps().count("no-allowlisted-repair"), 3)
        self.assertEqual(set(resp.REPAIRS), {FIVE_XX})

    def test_pending_alert_is_not_repaired(self):
        sb.inject_fault(self.root)
        before = self.config_bytes()
        self.event(state="pending")
        [result] = self.responder().run_cycle()
        self.assertEqual(result["outcome"], "not-firing")
        self.assertEqual(self.config_bytes(), before)


class SandboxSafety(unittest.TestCase):
    def assertRefused(self, path):
        with self.assertRaises(resp.SandboxError):
            resp.Sandbox(path)

    def test_repository_and_non_temp_paths_are_refused(self):
        self.assertRefused(ROOT)
        self.assertRefused(AGENT_DIR)
        self.assertRefused(Path(tempfile.gettempdir()))

    def test_unmarked_or_forged_temp_directories_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertRefused(tmp)
            (Path(tmp) / sb.SPOOL_NAME).mkdir()
            marker = Path(tmp) / sb.MARKER_NAME
            for content in ("", "{}", json.dumps({"created_by": sb.CREATED_BY,
                                                  "synthetic": True, "nonce": "short"})):
                marker.write_text(content, encoding="utf-8")
                self.assertRefused(tmp)

    def test_cli_refuses_the_repository_and_writes_nothing(self):
        before = sorted(p.name for p in ROOT.iterdir())
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = resp.main(["--sandbox", str(ROOT), "--once"], clock=clock)
        self.assertEqual(code, 2)
        self.assertIn("refused", err.getvalue())
        self.assertEqual(sorted(p.name for p in ROOT.iterdir()), before)


class SymlinkSafety(SandboxCase):
    def symlink(self, link, target, directory=False):
        try:
            os.symlink(target, link, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("this platform does not allow creating symlinks")

    def test_symlinked_sandbox_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "link"
            self.symlink(link, self.root, directory=True)
            with self.assertRaises(resp.SandboxError):
                resp.Sandbox(link)

    def test_symlinked_config_escape_is_refused_before_any_change(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "victim.json"
            target.write_text('{"fault_5xx": true}', encoding="utf-8")
            config = self.root / sb.CONFIG_NAME
            config.unlink()
            self.symlink(config, target)
            self.event()
            with self.assertRaises(resp.SandboxError):
                self.responder().run_cycle()
            self.assertEqual(target.read_text(encoding="utf-8"), '{"fault_5xx": true}')

    def test_symlinked_spool_event_is_ignored(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "event.json"
            target.write_text("{}", encoding="utf-8")
            self.symlink(self.root / sb.SPOOL_NAME / "linked.json", target)
            self.assertEqual(self.responder().run_cycle(), [])
            self.assertEqual(self.steps(), ["event-ignored"])


class Duplicates(SandboxCase):
    # Different starts_at values make the files differ, so the second event is
    # caught by its fingerprint, not by its content hash.
    def duplicate(self, fingerprint, name, starts_at):
        sb.write_alert_event(self.root, FIVE_XX, "warning", starts_at,
                             fingerprint=fingerprint, name=name)

    def test_same_fingerprint_is_acted_on_once(self):
        sb.inject_fault(self.root)
        self.duplicate("aaaaaaaaaaaaaaaa", "first.json", "2026-10-26T11:50:00Z")
        self.duplicate("aaaaaaaaaaaaaaaa", "second.json", "2026-10-26T11:51:00Z")
        results = self.responder().run_cycle()
        self.assertEqual(len(results), 1)
        self.assertEqual(self.steps().count("repair-applied"), 1)
        self.assertEqual(self.steps().count("duplicate-skipped"), 1)

    def test_duplicate_protection_survives_a_new_responder(self):
        sb.inject_fault(self.root)
        self.duplicate("bbbbbbbbbbbbbbbb", "first.json", "2026-10-26T11:50:00Z")
        self.responder().run_cycle()
        sb.inject_fault(self.root)
        self.duplicate("bbbbbbbbbbbbbbbb", "again.json", "2026-10-26T11:52:00Z")
        self.assertEqual(self.responder().run_cycle(), [])
        self.assertEqual(self.steps().count("repair-applied"), 1)
        self.assertEqual(self.steps().count("duplicate-skipped"), 1)
        self.assertEqual(json.loads(self.config_bytes())["fault_5xx"], True)


class AuditPrivacy(SandboxCase):
    def test_audit_holds_no_contents_paths_or_payloads(self):
        config = json.loads(self.config_bytes())
        config["fault_5xx"] = True
        config["note"] = "SENTINEL-CONFIG-CONTENT"
        (self.root / sb.CONFIG_NAME).write_text(json.dumps(config), encoding="utf-8")
        self.event()
        bad = {"schema_version": 1, "synthetic": True, "source": sb.EVENT_SOURCE,
               "alertname": FIVE_XX, "severity": "warning", "state": "firing",
               "starts_at": STARTS, "fingerprint": "cccccccccccccccc",
               "request_body": "SENTINEL-PAYLOAD password=hunter2"}
        (self.root / sb.SPOOL_NAME / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        self.responder().run_cycle()

        text = (self.root / sb.AUDIT_NAME).read_text(encoding="utf-8")
        for secret in ("SENTINEL-CONFIG-CONTENT", "SENTINEL-PAYLOAD", "hunter2",
                       str(self.root), self.root.name):
            with self.subTest(secret):
                self.assertNotIn(secret, text)
        for entry in self.audit():
            self.assertLessEqual(set(entry) - {"seq", "time_utc", "step"}, resp.AUDIT_FIELDS)

    def test_unknown_audit_fields_are_refused(self):
        audit = self.responder().audit
        with self.assertRaises(ValueError):
            audit.record("woke", config_contents="x")


class Thresholds(unittest.TestCase):
    def test_thresholds_match_the_alert_rule(self):
        text = RULES.read_text(encoding="utf-8")
        block = text.split("- alert: CareerPilotHigh5xxRate", 1)[1].split("- alert:", 1)[0]
        self.assertEqual(float(re.search(r"\)\s*>\s*([0-9.]+)", block).group(1)),
                         resp.RATIO_THRESHOLD)
        self.assertEqual(int(re.search(r">=\s*(\d+)", block).group(1)), resp.MIN_REQUESTS)
        self.assertGreaterEqual(resp.VERIFY_REQUESTS, resp.MIN_REQUESTS)

    def test_condition_and_verification_boundaries(self):
        self.assertFalse(resp.alert_condition(9, 9))
        self.assertTrue(resp.alert_condition(20, 2))
        self.assertFalse(resp.alert_condition(20, 1))
        self.assertTrue(resp.verification_passed(20, 1))
        self.assertFalse(resp.verification_passed(20, 2))
        self.assertFalse(resp.verification_passed(9, 0))


class SourceBoundaries(unittest.TestCase):
    def test_no_network_database_shell_or_docker_access(self):
        banned = ("subprocess", "socket", "urllib", "http", "requests", "sqlite3", "psycopg",
                  "sqlalchemy", "docker", "asyncio")
        for path in (RESPONDER, SANDBOX_MODULE):
            source = path.read_text(encoding="utf-8")
            for module in banned:
                with self.subTest(path=path.name, module=module):
                    self.assertNotRegex(source, rf"(?m)^\s*(import|from) {module}\b")
            self.assertNotRegex(source, r"https?://")
        responder = RESPONDER.read_text(encoding="utf-8")
        for module in ("os", "shutil"):
            self.assertNotRegex(responder, rf"(?m)^\s*(import|from) {module}\b")


class CommandLine(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = resp.main(list(argv), clock=clock, sleep=lambda s: None)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_mode_and_sandbox_are_required(self):
        for argv in ([], ["--once"], ["--watch"], ["--sandbox", "x"],
                     ["--once", "--watch", "--sandbox", "x"]):
            with self.subTest(argv):
                self.assertEqual(self.run_main(*argv)[0], 2)

    def test_watch_bounds_are_enforced(self):
        root = sb.create_sandbox()
        self.addCleanup(sb.remove_sandbox, root)
        for extra in (["--interval", "0"], ["--interval", "61"], ["--max-cycles", "0"],
                      ["--max-cycles", "101"]):
            with self.subTest(extra):
                self.assertEqual(self.run_main("--sandbox", str(root), "--watch", *extra)[0], 2)

    def test_demo_repairs_and_removes_its_sandbox(self):
        def sandboxes():
            return set(Path(tempfile.gettempdir()).glob("careerpilot-oncall-*"))

        existing = sandboxes()
        code, out, _ = self.run_main("--demo", "--json")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertTrue(result["synthetic"])
        self.assertEqual([r["outcome"] for r in result["results"]], ["resolved"])
        self.assertEqual(result["results"][0]["report"]["status"], "resolved")
        self.assertLessEqual(sandboxes(), existing)

    def test_demo_cannot_target_an_existing_sandbox(self):
        self.assertEqual(self.run_main("--demo", "--sandbox", "x")[0], 2)

    def test_open_incident_exits_1(self):
        root = sb.create_sandbox()
        self.addCleanup(sb.remove_sandbox, root)
        sb.write_alert_event(root, "CareerPilotOtelCollectorDown", "warning", STARTS)
        code, out, _ = self.run_main("--sandbox", str(root), "--once")
        self.assertEqual(code, 1)
        self.assertIn("report-only", out)

    def test_demo_process_runs_offline(self):
        result = subprocess.run([sys.executable, str(RESPONDER), "--demo"], capture_output=True,
                                text=True, encoding="utf-8", timeout=60, cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Responder outcome: resolved", result.stdout)
        self.assertIn("Demo sandbox removed.", result.stdout)


class SandboxRemoval(unittest.TestCase):
    def test_remove_refuses_unmarked_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                sb.remove_sandbox(tmp)
            self.assertTrue(Path(tmp).exists())
        with self.assertRaises(ValueError):
            sb.remove_sandbox(ROOT)


if __name__ == "__main__":
    unittest.main()
