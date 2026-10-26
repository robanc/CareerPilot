"""Tests for custom-agent/prometheus_alert_adapter.py (stdlib unittest; mocked HTTP only).

No live requests, network, database, Docker, or running services. Responses come
from fake openers or from fake urllib handlers that replace the HTTP transport.
Run from the repository root:
    python -m unittest discover -s custom-agent/tests
"""

import contextlib
import email.message
import http.client
import io
import json
import os
import re
import subprocess
import sys
import unittest
from unittest import mock
import urllib.error
import urllib.request
import urllib.response
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "custom-agent" / "prometheus_alert_adapter.py"
sys.path.insert(0, str(ADAPTER.parent))

import oncall_investigator as oi  # noqa: E402
import prometheus_alert_adapter as pa  # noqa: E402

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)


def prom_alert(name, state="firing", active_at="2026-10-25T20:00:00.123456789Z",
               severity=None, **labels):
    return {"labels": {"alertname": name, "severity": severity or pa.ALERTS.get(name, "warning"),
                       **labels},
            "annotations": {"summary": "s", "description": "d"},
            "state": state, "activeAt": active_at, "value": "1e+00"}


def body(*alerts, status="success"):
    return json.dumps({"status": status, "data": {"alerts": list(alerts)}}).encode("utf-8")


class FakeResponse:
    def __init__(self, content=b"", status=200, url=pa.ENDPOINT, headers=None):
        self.content, self.status, self.url = content, status, url
        self.headers = headers or {}
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self.content if size < 0 else self.content[:size]

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self, outcome):
        self.outcome, self.requests = outcome, []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeTransport(urllib.request.BaseHandler):
    """Replaces the HTTP transport inside a real urllib opener; never connects."""

    handler_order = 100  # runs before urllib's own HTTPHandler

    def __init__(self, code, content=b"", location=None):
        self.code, self.content, self.location, self.calls = code, content, location, []

    def http_open(self, req):
        self.calls.append(req.full_url)
        headers = email.message.Message()
        if self.location:
            headers["Location"] = self.location
        response = urllib.response.addinfourl(io.BytesIO(self.content), headers,
                                              req.full_url, self.code)
        response.msg = "OK" if self.code == 200 else "Redirect"
        return response


def run_main(outcome, argv=("--connect",)):
    """Run main with a fake opener, or with a real urllib opener given directly."""
    opener = outcome if isinstance(outcome, urllib.request.OpenerDirector) else FakeOpener(outcome)
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = pa.main(list(argv), opener=opener, now=NOW)
    return code, stdout.getvalue(), stderr.getvalue(), opener


class OptInAndRequest(unittest.TestCase):
    def test_default_makes_no_connection(self):
        code, out, err, opener = run_main(FakeResponse(body()), argv=())
        self.assertEqual(code, 1)
        self.assertEqual(opener.requests, [])
        self.assertEqual(out, "")
        self.assertIn("no connection made", err)

    def test_default_cli_process_makes_no_connection(self):
        result = subprocess.run([sys.executable, str(ADAPTER)], capture_output=True, text=True,
                                encoding="utf-8", timeout=60, cwd=str(ROOT))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")

    def test_connect_sends_one_bounded_get_to_the_fixed_endpoint(self):
        response = FakeResponse(body())
        code, _, _, opener = run_main(response)
        self.assertEqual(code, 0)
        self.assertEqual(len(opener.requests), 1)
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:9090/api/v1/alerts")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertFalse(request.has_header("Authorization"))
        self.assertEqual(timeout, pa.TIMEOUT_SECONDS)
        self.assertLessEqual(pa.TIMEOUT_SECONDS, 5)
        self.assertEqual(response.read_sizes, [pa.MAX_RESPONSE_BYTES + 1])

    def test_no_option_accepts_a_url_or_query(self):
        for extra in (["--url", "http://example.invalid"], ["--query", "up"]):
            with self.subTest(extra), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    pa.main(["--connect", *extra], opener=FakeOpener(FakeResponse(body())))

    def test_opener_ignores_environment_proxies_and_refuses_redirects(self):
        # An empty ProxyHandler replaces urllib's environment-based default and,
        # having no proxies, registers no proxy handling at all.
        proxy_env = {"HTTP_PROXY": "http://proxy.invalid:3128",
                     "http_proxy": "http://proxy.invalid:3128"}
        with mock.patch.dict(os.environ, proxy_env):
            opener = pa.build_opener()
        self.assertFalse(any(isinstance(h, urllib.request.ProxyHandler)
                             for h in opener.handlers))
        self.assertTrue(any(isinstance(h, pa._RefuseRedirects) for h in opener.handlers))


class Snapshot(unittest.TestCase):
    def test_all_four_alerts_are_sanitized_and_collector_first(self):
        content = body(
            prom_alert("CareerPilotBackendTelemetryMissing", active_at="2026-10-25T20:05:00Z"),
            prom_alert("CareerPilotHigh5xxRate", state="pending",
                       active_at="2026-10-25T22:01:02.5+02:00"),
            prom_alert("CareerPilotHighAverageLatency"),
            prom_alert("CareerPilotOtelCollectorDown", job="careerpilot-otel-collector",
                       instance="otel-collector:8889"))
        code, out, _, _ = run_main(FakeResponse(content))
        self.assertEqual(code, 0)
        snapshot = json.loads(out)
        self.assertEqual(snapshot["source"], "live-prometheus")
        self.assertIs(snapshot["synthetic"], False)
        self.assertEqual(snapshot["retrieved_at_utc"], "2026-10-25T21:00:00Z")
        self.assertEqual(snapshot["alert_count"], 4)
        self.assertEqual([a["alertname"] for a in snapshot["alerts"]], list(pa.ALERTS))
        for item in snapshot["alerts"]:
            self.assertEqual(set(item), {"alertname", "severity", "state", "active_at_utc"})
        by_name = {a["alertname"]: a for a in snapshot["alerts"]}
        self.assertEqual(by_name["CareerPilotHigh5xxRate"]["active_at_utc"],
                         "2026-10-25T20:01:02Z")
        self.assertEqual(by_name["CareerPilotHigh5xxRate"]["state"], "pending")
        self.assertEqual(by_name["CareerPilotBackendTelemetryMissing"]["severity"], "info")

    def test_annotations_unexpected_labels_and_values_are_dropped(self):
        alert = prom_alert("CareerPilotHigh5xxRate", secret_token="tok-123",
                           request_body="{\"resume_text\": \"Fictional resume\"}")
        alert["annotations"] = {"description": "password=hunter2",
                                "resume": "Fictional resume: Python"}
        alert["value"] = "4.2e-01"
        code, out, _, _ = run_main(FakeResponse(body(alert)))
        self.assertEqual(code, 0)
        for text in ("tok-123", "hunter2", "Fictional resume", "secret_token", "request_body",
                     "annotations", "4.2e-01", "description"):
            with self.subTest(text):
                self.assertNotIn(text, out)

    def test_empty_alerts_is_an_empty_snapshot_not_a_health_claim(self):
        code, out, _, _ = run_main(FakeResponse(body()))
        self.assertEqual(code, 0)
        snapshot = json.loads(out)
        self.assertEqual(snapshot["alert_count"], 0)
        self.assertEqual(snapshot["alerts"], [])
        self.assertIn("does not show that the system is healthy", snapshot["notes"][0])
        self.assertNotIn("status", snapshot)
        self.assertNotIn("resolved", out.lower())

    def test_snapshot_is_not_accepted_by_the_synthetic_investigator(self):
        _, out, _, _ = run_main(FakeResponse(body(prom_alert("CareerPilotHigh5xxRate"))))
        with self.assertRaises(oi.InputError):
            oi.parse_evidence(json.loads(out))

    def test_full_urllib_pipeline_with_a_fake_transport(self):
        transport = FakeTransport(200, body(prom_alert("CareerPilotOtelCollectorDown")))
        code, out, _, _ = run_main(pa.build_opener(transport))
        self.assertEqual(code, 0)
        self.assertEqual(transport.calls, [pa.ENDPOINT])
        self.assertEqual(json.loads(out)["alerts"][0]["alertname"],
                         "CareerPilotOtelCollectorDown")


class RejectedResponses(unittest.TestCase):
    def assertRejected(self, outcome, *secrets):
        code, out, err, _ = run_main(outcome)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("rejected", err)
        for secret in secrets:
            self.assertNotIn(secret, err)
        return err

    def test_malformed_json_and_encoding(self):
        for content in (b"{not json", b"", b"\xff\xfe\x00", b"[]", b"null"):
            with self.subTest(content):
                self.assertRejected(FakeResponse(content))

    def test_bad_api_status_or_structure(self):
        for content in (body(status="error"),
                        json.dumps({"status": "success"}).encode(),
                        json.dumps({"status": "success", "data": {"alerts": {}}}).encode(),
                        json.dumps({"status": "success", "data": []}).encode()):
            with self.subTest(content):
                self.assertRejected(FakeResponse(content))

    def test_oversized_response(self):
        big = b" " * (pa.MAX_RESPONSE_BYTES + 1)
        self.assertRejected(FakeResponse(big))
        declared = FakeResponse(body(), headers={"Content-Length": str(10 * 1024 * 1024)})
        self.assertRejected(declared)
        self.assertEqual(declared.read_sizes, [])

    def test_too_many_alerts(self):
        alerts = [prom_alert("CareerPilotHigh5xxRate")] * (pa.MAX_ALERTS + 1)
        self.assertRejected(FakeResponse(body(*alerts)))

    def test_unknown_or_malformed_alerts(self):
        cases = {
            "unknown alert": prom_alert("LeakyCustomerAlert"),
            "non-string name": prom_alert(["CareerPilotHigh5xxRate"], severity="warning"),
            "severity mismatch": prom_alert("CareerPilotHigh5xxRate", severity="critical"),
            "info vs warning": prom_alert("CareerPilotBackendTelemetryMissing",
                                          severity="warning"),
            "no labels": {"state": "firing", "activeAt": "2026-10-25T20:00:00Z"},
            "not an object": "CareerPilotHigh5xxRate",
        }
        for label, alert in cases.items():
            with self.subTest(label):
                self.assertRejected(FakeResponse(body(alert)), "LeakyCustomerAlert")

    def test_invalid_states(self):
        for state in ("inactive", "resolved", "FIRING", None):
            with self.subTest(state):
                self.assertRejected(FakeResponse(body(
                    prom_alert("CareerPilotHigh5xxRate", state=state))))

    def test_bad_timestamps(self):
        for value in ("2026-10-25T20:00:00", "2026-10-25 20:00:00Z", "2026-02-30T00:00:00Z",
                      "0001-01-01T00:00:00", "yesterday", 1761422400, None):
            with self.subTest(value):
                self.assertRejected(FakeResponse(body(
                    prom_alert("CareerPilotHigh5xxRate", active_at=value))))

    def test_unexpected_http_status_or_url(self):
        self.assertRejected(FakeResponse(body(), status=204))
        self.assertRejected(FakeResponse(body(), url="http://127.0.0.1:9090/elsewhere"))

    def test_redirect_is_refused_by_the_real_redirect_handler(self):
        transport = FakeTransport(302, location="http://example.invalid/api/v1/alerts")
        err = self.assertRejected(pa.build_opener(transport))
        self.assertIn("redirect refused", err)
        self.assertEqual(transport.calls, [pa.ENDPOINT])

    def test_network_failures(self):
        failures = [
            urllib.error.URLError(ConnectionRefusedError()),
            TimeoutError("timed out"),
            ConnectionResetError(),
            http.client.IncompleteRead(b"partial secret"),
            urllib.error.HTTPError(pa.ENDPOINT, 503, "Service Unavailable", None, None),
        ]
        for failure in failures:
            with self.subTest(type(failure).__name__):
                self.assertRejected(failure, "partial secret")


class SourceBoundaries(unittest.TestCase):
    def test_adapter_has_no_database_shell_or_file_access(self):
        source = ADAPTER.read_text(encoding="utf-8")
        for module in ("subprocess", "socket", "os", "shutil", "pathlib", "sqlite3",
                       "psycopg", "sqlalchemy", "requests"):
            with self.subTest(module):
                self.assertNotRegex(source, rf"(?m)^\s*(import|from) {module}\b")
        self.assertEqual(set(re.findall(r"https?://[^\s;\"')]+", source)), {pa.ENDPOINT})


if __name__ == "__main__":
    unittest.main()
