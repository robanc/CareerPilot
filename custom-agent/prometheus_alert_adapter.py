"""CareerPilot Prometheus alert adapter: a read-only, opt-in live alert snapshot.

A deterministic adapter (no LLM). Only with --connect does it send ONE HTTP
GET to the fixed local endpoint http://127.0.0.1:9090/api/v1/alerts; it then
prints a sanitized JSON snapshot of the CareerPilot alerts Prometheus reports
as pending or firing. Without --connect it makes no connection at all.

Boundaries:
  endpoint     fixed; no user-supplied URLs or PromQL, no redirects, no
               proxies, no credentials
  limits       3-second timeout, 256 KiB response, 100 alerts
  validation   API status, the alert list, the four CareerPilot alert names,
               their documented severities, states, and timezone-aware
               activeAt timestamps; anything unexpected rejects the response
  output       alert name, severity, state, and UTC activeAt only; never
               annotations, other labels, or values. Labelled
               source=live-prometheus and synthetic=false
  scope        a snapshot only: no health conclusion and no resolution claim.
               Not input for oncall_investigator.py, which accepts synthetic
               evidence only. No database, Docker, shell, file writes, or
               remediation.

Usage, from the repository root:
    python custom-agent/prometheus_alert_adapter.py --connect
Exit code 0 when a snapshot is printed, 1 when --connect was not given,
2 when the request or the response is rejected.
"""

import argparse
import http.client
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "http://127.0.0.1:9090/api/v1/alerts"
TIMEOUT_SECONDS = 3
MAX_RESPONSE_BYTES = 256 * 1024
MAX_ALERTS = 100

# Documented severities, in investigation order (Collector first, runbook 5.4).
ALERTS = {
    "CareerPilotOtelCollectorDown": "warning",
    "CareerPilotHigh5xxRate": "warning",
    "CareerPilotHighAverageLatency": "warning",
    "CareerPilotBackendTelemetryMissing": "info",
}
# /api/v1/alerts lists active alerts only.
STATES = ("pending", "firing")
ACTIVE_AT = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})")

EMPTY_NOTE = ("No CareerPilot alerts were pending or firing when the snapshot was taken. "
              "This does not show that the system is healthy: rules may not be evaluated, "
              "or telemetry may not be exported.")
NOTES = (
    "Snapshot of alerts Prometheus reported as pending or firing; not a health assessment.",
    "Incident resolution is not assessed.",
    "Not valid input for oncall_investigator.py, which accepts synthetic evidence only.",
)


class AdapterError(RuntimeError):
    """The request failed or the response was rejected. Never quotes response content."""


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AdapterError(f"redirect refused (HTTP {code})")


def build_opener(*handlers):
    """An opener with proxies disabled and redirects refused.

    Extra handlers are for tests only; the CLI never passes any.
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _RefuseRedirects(),
                                       *handlers)


def fetch(opener=None):
    """Send the single GET request and return the bounded response body."""
    opener = opener or build_opener()
    request = urllib.request.Request(ENDPOINT, method="GET",
                                     headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.geturl() != ENDPOINT:
                raise AdapterError("response came from an unexpected URL")
            if response.status != 200:
                raise AdapterError(f"unexpected HTTP status {response.status}")
            length = response.headers.get("Content-Length", "")
            if length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
                raise AdapterError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except AdapterError:
        raise
    except urllib.error.HTTPError as exc:
        raise AdapterError(f"Prometheus returned HTTP {exc.code}") from None
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as exc:
        raise AdapterError(f"could not reach Prometheus ({type(exc).__name__})") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise AdapterError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
    return body


def _utc(value, path):
    match = ACTIVE_AT.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise AdapterError(f"{path} must be a timestamp with a timezone")
    base, fraction, zone = match.groups()
    # Prometheus sends nanoseconds; datetime keeps microseconds.
    iso = base + (fraction or "")[:7] + ("+00:00" if zone == "Z" else zone)
    try:
        return datetime.fromisoformat(iso).astimezone(timezone.utc)
    except ValueError:
        raise AdapterError(f"{path} is not a valid date and time") from None


def parse_alerts(body):
    """Validate the API response and return sanitized alerts, Collector first."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AdapterError("response is not valid UTF-8 JSON") from None
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise AdapterError("Prometheus API status is not success")
    data = payload.get("data")
    alerts = data.get("alerts") if isinstance(data, dict) else None
    if not isinstance(alerts, list):
        raise AdapterError("response has no alert list")
    if len(alerts) > MAX_ALERTS:
        raise AdapterError(f"response lists more than {MAX_ALERTS} alerts")

    result = []
    for i, alert in enumerate(alerts):
        path = f"alerts[{i}]"
        labels = alert.get("labels") if isinstance(alert, dict) else None
        if not isinstance(labels, dict):
            raise AdapterError(f"{path} has no labels")
        name = labels.get("alertname")
        if not isinstance(name, str) or name not in ALERTS:
            raise AdapterError(f"{path} is not a CareerPilot alert")
        if labels.get("severity") != ALERTS[name]:
            raise AdapterError(f"{path} does not have the documented severity")
        state = alert.get("state")
        if state not in STATES:
            raise AdapterError(f"{path}.state must be one of: {', '.join(STATES)}")
        active = _utc(alert.get("activeAt"), f"{path}.activeAt")
        result.append({"alertname": name, "severity": ALERTS[name], "state": state,
                       "active_at_utc": active.strftime("%Y-%m-%dT%H:%M:%SZ")})
    order = list(ALERTS)
    result.sort(key=lambda a: (order.index(a["alertname"]), a["active_at_utc"]))
    return result


def build_snapshot(alerts, retrieved_at):
    return {
        "source": "live-prometheus",
        "synthetic": False,
        "endpoint": ENDPOINT,
        "retrieved_at_utc": retrieved_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "alert_count": len(alerts),
        "alerts": alerts,
        "notes": ([EMPTY_NOTE] if not alerts else []) + list(NOTES),
    }


def main(argv=None, opener=None, now=None):
    parser = argparse.ArgumentParser(
        description="CareerPilot Prometheus alert adapter (read-only, opt-in).")
    parser.add_argument("--connect", action="store_true",
                        help=f"Send one GET request to {ENDPOINT}.")
    args = parser.parse_args(argv)
    if not args.connect:
        print(f"prometheus alert adapter: no connection made; pass --connect to query "
              f"{ENDPOINT}", file=sys.stderr)
        return 1

    retrieved_at = now or datetime.now(timezone.utc)
    try:
        alerts = parse_alerts(fetch(opener))
    except AdapterError as exc:
        print(f"prometheus alert adapter: rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(build_snapshot(alerts, retrieved_at), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
