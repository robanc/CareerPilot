"""Tests for custom-agent/oncall_investigator.py (stdlib unittest; synthetic input only).

No network, database, Docker, or running services. Run from the repository root:
    python -m unittest discover -s custom-agent/tests
"""

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "custom-agent" / "oncall_investigator.py"
RULES = ROOT / "monitoring" / "alerts" / "careerpilot.rules.yml"
sys.path.insert(0, str(AGENT.parent))

import oncall_investigator as oi  # noqa: E402

T0 = "2026-10-25T20:00:00Z"
T1 = "2026-10-25T20:10:00Z"
T2 = "2026-10-25T20:20:00Z"
TRACE_ID = "0123456789abcdef0123456789abcdef"


def alert(name, state="firing", active_at=T0, **extra):
    return {"alertname": name, "state": state, "active_at": active_at, **extra}


def evidence_doc(*alerts, **evidence):
    doc = {"schema_version": 1, "synthetic": True, "incident_id": "2026-10-25-1",
           "alerts": list(alerts)}
    if evidence:
        doc["evidence"] = evidence
    return doc


def run(doc):
    return oi.investigate(oi.parse_evidence(doc))


FULL_VERIFICATION = {"alert_inactive": True, "incident_check_passed": True,
                     "no_unapproved_changes": True, "telemetry_visible": True}


class KnownAlerts(unittest.TestCase):
    def test_alerts_and_severities_match_the_rules_file(self):
        text = RULES.read_text(encoding="utf-8")
        names = re.findall(r"^\s*- alert: (\w+)", text, re.MULTILINE)
        severities = re.findall(r"^\s*severity: (\w+)", text, re.MULTILINE)
        self.assertEqual(dict(zip(names, severities)),
                         {name: info["severity"] for name, info in oi.ALERTS.items()})


class SingleAlerts(unittest.TestCase):
    def test_each_alert_is_reported_with_its_severity_and_runbook_section(self):
        cases = {
            "CareerPilotHigh5xxRate": ("warning", "incident", "5.1"),
            "CareerPilotHighAverageLatency": ("warning", "incident", "5.2"),
            "CareerPilotOtelCollectorDown": ("warning", "incident", "5.4"),
            "CareerPilotBackendTelemetryMissing": ("info", "needs-investigation", "5.3 and 6"),
        }
        for name, (severity, classification, section) in cases.items():
            with self.subTest(name):
                report = run(evidence_doc(alert(name)))
                self.assertEqual(report["alert"], name)
                self.assertEqual(report["severity"], severity)
                self.assertEqual(report["classification"], classification)
                self.assertEqual(report["alerts"][0]["runbook_section"], section)
                self.assertEqual(report["root_cause"], "unknown")
                self.assertEqual(report["status"], "open")
                self.assertIsNone(report["resolved_utc"])

    def test_pending_alert_is_not_an_incident_yet(self):
        report = run(evidence_doc(alert("CareerPilotHigh5xxRate", state="pending")))
        self.assertEqual(report["classification"], "pending")
        self.assertEqual(report["status"], "open")


class CollectorPriority(unittest.TestCase):
    def test_collector_down_is_investigated_first(self):
        report = run(evidence_doc(alert("CareerPilotHigh5xxRate"),
                                  alert("CareerPilotBackendTelemetryMissing"),
                                  alert("CareerPilotOtelCollectorDown", active_at=T1)))
        self.assertEqual(report["alert"], "CareerPilotOtelCollectorDown")
        order = [a["alertname"] for a in report["alerts"]]
        self.assertEqual(order[0], "CareerPilotOtelCollectorDown")
        telemetry = next(a for a in report["alerts"]
                         if a["alertname"] == "CareerPilotBackendTelemetryMissing")
        self.assertEqual(telemetry["classification"], "incident")
        self.assertIn("Collector", telemetry["note"])
        self.assertIn("Re-check CareerPilotBackendTelemetryMissing after the Collector recovers.",
                      report["follow_ups"])

    def test_collector_scrape_failure_evidence_makes_missing_telemetry_an_incident(self):
        report = run(evidence_doc(alert("CareerPilotBackendTelemetryMissing"),
                                  otlp_export="disabled", collector_up=False))
        self.assertEqual(report["classification"], "incident")

    def test_collector_priority_does_not_set_a_root_cause(self):
        report = run(evidence_doc(alert("CareerPilotOtelCollectorDown"),
                                  alert("CareerPilotBackendTelemetryMissing")))
        self.assertEqual(report["root_cause"], "unknown")


class MissingTelemetry(unittest.TestCase):
    def test_explicit_evidence_makes_missing_telemetry_expected(self):
        for flags in ({"otlp_export": "disabled"}, {"backend_running": False},
                      {"backend_served_requests": False}):
            with self.subTest(flags):
                report = run(evidence_doc(alert("CareerPilotBackendTelemetryMissing"), **flags))
                self.assertEqual(report["classification"], "expected")
                self.assertEqual(report["status"], "expected-behavior")
                self.assertEqual(report["verification"]["status"], "not-applicable")

    def test_without_evidence_missing_telemetry_needs_investigation(self):
        for evidence in ({}, {"otlp_export": "unknown"},
                         {"otlp_export": "enabled", "backend_running": True,
                          "backend_served_requests": True, "collector_up": True}):
            with self.subTest(evidence):
                report = run(evidence_doc(alert("CareerPilotBackendTelemetryMissing"), **evidence))
                self.assertEqual(report["classification"], "needs-investigation")
                self.assertEqual(report["status"], "open")

    def test_docker_backend_needs_investigation_and_cites_the_unverified_assumption(self):
        report = run(evidence_doc(alert("CareerPilotBackendTelemetryMissing"),
                                  otlp_export="enabled", backend_in_docker=True))
        self.assertEqual(report["classification"], "needs-investigation")
        self.assertIn("unverified", report["alerts"][0]["note"])

    def test_expected_telemetry_does_not_hide_a_real_incident(self):
        report = run(evidence_doc(alert("CareerPilotBackendTelemetryMissing"),
                                  alert("CareerPilotHigh5xxRate"), otlp_export="disabled"))
        self.assertEqual(report["alert"], "CareerPilotHigh5xxRate")
        self.assertEqual(report["classification"], "incident")
        self.assertTrue(any("inconsistent" in item for item in report["follow_ups"]))


class RootCauseAndResolution(unittest.TestCase):
    def test_root_cause_only_when_established(self):
        base = [alert("CareerPilotHigh5xxRate")]
        unestablished = run(evidence_doc(*base, root_cause={"established": False,
                                                            "summary": "maybe the database"}))
        self.assertEqual(unestablished["root_cause"], "unknown")
        established = run(evidence_doc(*base, root_cause={
            "established": True, "summary": "Synthetic route raised an unhandled exception."}))
        self.assertEqual(established["root_cause"],
                         "Synthetic route raised an unhandled exception.")

    def test_inactive_alert_without_verification_is_not_resolved(self):
        report = run(evidence_doc(alert("CareerPilotHigh5xxRate", state="inactive",
                                        resolved_at=T1)))
        self.assertEqual(report["status"], "open")
        self.assertEqual(report["verification"]["status"], "not-verified")
        self.assertIsNone(report["resolved_utc"])

    def test_complete_verification_resolves(self):
        report = run(evidence_doc(alert("CareerPilotHigh5xxRate", state="inactive",
                                        resolved_at=T1),
                                  otlp_export="enabled", verification=FULL_VERIFICATION))
        self.assertEqual(report["status"], "resolved")
        self.assertEqual(report["resolved_utc"], T1)
        self.assertEqual(report["verification"]["missing"], [])

    def test_incomplete_or_inconsistent_verification_is_not_resolved(self):
        inactive = alert("CareerPilotHigh5xxRate", state="inactive", resolved_at=T1)
        cases = {
            "telemetry not visible": ([inactive], {**FULL_VERIFICATION,
                                                   "telemetry_visible": None}),
            "unapproved synthetic request": ([inactive], {**FULL_VERIFICATION,
                                                          "synthetic_request_used": True}),
            "alert still firing": ([alert("CareerPilotHigh5xxRate")], FULL_VERIFICATION),
        }
        for label, (alerts, verification) in cases.items():
            with self.subTest(label):
                report = run(evidence_doc(*alerts, otlp_export="enabled",
                                          verification=verification))
                self.assertEqual(report["status"], "open")
                self.assertEqual(report["verification"]["status"], "not-verified")

    def test_disabled_otlp_does_not_require_telemetry_for_verification(self):
        verification = {**FULL_VERIFICATION, "telemetry_visible": None}
        report = run(evidence_doc(alert("CareerPilotOtelCollectorDown", state="inactive",
                                        resolved_at=T1),
                                  otlp_export="disabled", verification=verification))
        self.assertEqual(report["status"], "resolved")

    def test_timeline_is_sorted_and_normalized_to_utc(self):
        report = run(evidence_doc(
            alert("CareerPilotHigh5xxRate", active_at="2026-10-25T22:00:00+02:00"),
            observations=[{"time": T1, "source": "loki", "summary": "5xx log lines found.",
                           "trace_ids": [TRACE_ID]}],
            actions=[{"time": T2, "action": "Restarted the backend.",
                      "approval": "approved-by-developer"}]))
        self.assertEqual([t["time_utc"] for t in report["timeline"]], [T0, T1, T2])
        self.assertEqual(report["active_utc"], T0)


class MalformedInput(unittest.TestCase):
    def assertRejected(self, doc):
        with self.assertRaises(oi.InputError):
            oi.parse_evidence(doc)

    def test_unknown_alert_name_is_rejected(self):
        self.assertRejected(evidence_doc(alert("CareerPilotDiskFull")))

    def test_invalid_state_is_rejected(self):
        for state in ("resolved", "FIRING", "", None):
            with self.subTest(state):
                self.assertRejected(evidence_doc(alert("CareerPilotHigh5xxRate", state=state)))

    def test_malformed_timestamps_are_rejected(self):
        for value in ("2026-10-25 20:00:00Z", "2026-10-25T20:00:00", "2026-13-01T00:00:00Z",
                      "yesterday", 1761422400, None):
            with self.subTest(value):
                self.assertRejected(evidence_doc(alert("CareerPilotHigh5xxRate",
                                                       active_at=value)))

    def test_structural_errors_are_rejected(self):
        good = evidence_doc(alert("CareerPilotHigh5xxRate"))
        cases = {
            "not an object": [],
            "synthetic false": {**good, "synthetic": False},
            "wrong schema version": {**good, "schema_version": 2},
            "boolean schema version": {**good, "schema_version": True},
            "unknown top-level field": {**good, "command": "rm -rf /"},
            "no alerts": {**good, "alerts": []},
            "duplicate alert": evidence_doc(alert("CareerPilotHigh5xxRate"),
                                            alert("CareerPilotHigh5xxRate")),
            "severity mismatch": evidence_doc(alert("CareerPilotHigh5xxRate",
                                                    severity="critical")),
            "resolved before active": evidence_doc(alert("CareerPilotHigh5xxRate",
                                                         state="inactive", active_at=T1,
                                                         resolved_at=T0)),
            "resolved while firing": evidence_doc(alert("CareerPilotHigh5xxRate",
                                                        resolved_at=T1)),
            "bad incident id": {**good, "incident_id": "INC-1"},
            "unknown evidence field": evidence_doc(alert("CareerPilotHigh5xxRate"),
                                                   raw_payload={"x": 1}),
            "non-boolean flag": evidence_doc(alert("CareerPilotHigh5xxRate"),
                                             backend_running="yes"),
            "bad trace id": evidence_doc(alert("CareerPilotHigh5xxRate"), observations=[
                {"time": T0, "source": "tempo", "summary": "Trace opened.",
                 "trace_ids": ["not-a-trace"]}]),
            "unapproved action type": evidence_doc(alert("CareerPilotHigh5xxRate"), actions=[
                {"time": T0, "action": "Restarted the backend.", "approval": "self"}]),
        }
        for label, doc in cases.items():
            with self.subTest(label):
                self.assertRejected(doc)


class Privacy(unittest.TestCase):
    def observation(self, summary):
        return evidence_doc(alert("CareerPilotHigh5xxRate"), observations=[
            {"time": T0, "source": "developer", "summary": summary}])

    def test_secret_like_text_is_rejected_without_echoing_it(self):
        for text in ("password=hunter2", "Authorization: Bearer abc123",
                     "postgresql://admin:pw@db:5432/careerpilot", "-----BEGIN PRIVATE KEY",
                     "api_key leaked", "resume_text was logged"):
            with self.subTest(text):
                with self.assertRaises(oi.InputError) as caught:
                    oi.parse_evidence(self.observation(text))
                self.assertNotIn(text, str(caught.exception))

    def test_long_or_multiline_text_is_rejected(self):
        resume_like = "Fictional resume: Python, FastAPI, PostgreSQL. " * 10
        for text in (resume_like, "line one\nline two", "   "):
            with self.subTest(len(text)):
                with self.assertRaises(oi.InputError):
                    oi.parse_evidence(self.observation(text))

    def test_raw_content_fields_have_no_way_in(self):
        for field in ("request_body", "resume_text", "job_description", "labels"):
            with self.subTest(field):
                doc = evidence_doc(alert("CareerPilotHigh5xxRate"))
                doc["alerts"][0][field] = "synthetic"
                with self.assertRaises(oi.InputError):
                    oi.parse_evidence(doc)

    def test_report_contains_only_the_documented_fields(self):
        report = run(evidence_doc(alert("CareerPilotHigh5xxRate")))
        self.assertEqual(set(report), {
            "incident_id", "synthetic", "generated_by", "alert", "severity", "classification",
            "status", "active_utc", "resolved_utc", "alerts", "impact", "timeline",
            "evidence_summary", "root_cause", "actions_taken", "verification", "follow_ups",
            "developer_review_required"})

    def test_input_text_is_reported_as_data_not_executed(self):
        doc = self.observation("$(touch should-not-exist) && echo hi")
        before = copy.deepcopy(doc)
        report = run(doc)
        self.assertEqual(doc, before)
        self.assertIn("$(touch should-not-exist) && echo hi", oi.render_markdown(report))

    def test_agent_has_no_network_database_or_shell_imports(self):
        source = AGENT.read_text(encoding="utf-8")
        for module in ("subprocess", "socket", "urllib", "http", "requests", "sqlite3",
                       "psycopg", "sqlalchemy", "os"):
            with self.subTest(module):
                self.assertNotRegex(source, rf"(?m)^\s*(import|from) {module}\b")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.evidence = self.dir / "evidence.json"
        self.evidence.write_text(json.dumps(evidence_doc(alert("CareerPilotOtelCollectorDown"))),
                                 encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_agent(self, *args):
        return subprocess.run([sys.executable, str(AGENT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=60, cwd=str(self.dir))

    def test_prints_a_markdown_report(self):
        result = self.run_agent(str(self.evidence))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## Incident 2026-10-25-1", result.stdout)
        self.assertIn("**Alert:** CareerPilotOtelCollectorDown", result.stdout)
        self.assertIn("### Follow-ups", result.stdout)

    def test_prints_json(self):
        result = self.run_agent(str(self.evidence), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["alert"], "CareerPilotOtelCollectorDown")

    def test_rejected_input_exits_2(self):
        self.evidence.write_text('{"schema_version": 1, "synthetic": true, "alerts": '
                                 '[{"alertname": "Nope", "state": "firing", '
                                 '"active_at": "2026-10-25T20:00:00Z"}]}', encoding="utf-8")
        result = self.run_agent(str(self.evidence))
        self.assertEqual(result.returncode, 2)
        self.assertIn("rejected input", result.stderr)
        self.assertNotIn("Nope", result.stderr)

    def test_writes_only_a_new_output_file(self):
        output = self.dir / "report.md"
        result = self.run_agent(str(self.evidence), "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## Incident", output.read_text(encoding="utf-8"))

        output.write_text("keep me", encoding="utf-8")
        again = self.run_agent(str(self.evidence), "--output", str(output))
        self.assertEqual(again.returncode, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep me")

    def test_refuses_to_overwrite_the_evidence_file(self):
        original = self.evidence.read_text(encoding="utf-8")
        result = self.run_agent(str(self.evidence), "--output", str(self.evidence))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.evidence.read_text(encoding="utf-8"), original)

    def test_missing_evidence_file_exits_2(self):
        result = self.run_agent(str(self.dir / "absent.json"))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
