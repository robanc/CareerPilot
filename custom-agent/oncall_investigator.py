"""CareerPilot on-call investigator: a small, deterministic incident report generator.

A deterministic agent (no LLM). It reads ONE local JSON file of synthetic
alert evidence, named explicitly by the developer, validates it strictly, and
produces an incident report that follows monitoring/INCIDENT_RESPONSE.md.
It has no network, database, Docker, or shell access, takes no remediation
action, and never executes anything from its input. The only file it writes
is the report, and only when --output names a new file.

Rules (from the runbook):
  alerts          only the four alerts in monitoring/alerts/careerpilot.rules.yml,
                  with their documented severities
  priority        a Collector-down alert is investigated first (runbook 5.4)
  telemetry       missing backend telemetry is "needs-investigation" unless the
                  evidence explicitly shows an expected cause (runbook section 6)
  root cause      "unknown" unless the evidence establishes it; never inferred
                  from an alert name
  resolution      "resolved" only with complete verification evidence
                  (runbook section 8)
  privacy         strict schema: unknown fields are rejected, free text is short
                  and single-line, and secret-like text is rejected, so raw
                  payloads, request bodies, resume text, and job descriptions
                  have no way into the report

Usage, from the repository root:
    python custom-agent/oncall_investigator.py EVIDENCE.json [--json] [--output PATH]
Exit code 0 when a report is produced, 2 when the input or output is rejected.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 64 * 1024
MAX_TEXT = 200
MAX_ITEMS = 50

# Investigation priority: the Collector first (runbook 5.4), then runbook order.
ALERTS = {
    "CareerPilotOtelCollectorDown": {"severity": "warning", "runbook": "5.4"},
    "CareerPilotHigh5xxRate": {"severity": "warning", "runbook": "5.1"},
    "CareerPilotHighAverageLatency": {"severity": "warning", "runbook": "5.2"},
    "CareerPilotBackendTelemetryMissing": {"severity": "info", "runbook": "5.3 and 6"},
}
COLLECTOR = "CareerPilotOtelCollectorDown"
TELEMETRY = "CareerPilotBackendTelemetryMissing"
OTLP_METRIC_ALERTS = ("CareerPilotHigh5xxRate", "CareerPilotHighAverageLatency")

STATES = ("pending", "firing", "inactive")
SOURCES = ("prometheus", "grafana", "loki", "tempo", "developer")
APPROVALS = ("read-only", "approved-by-developer")
OTLP_STATES = ("enabled", "disabled", "unknown")
FLAGS = ("backend_running", "backend_served_requests", "backend_in_docker", "collector_up")
VERIFICATION_KEYS = ("alert_inactive", "incident_check_passed", "no_unapproved_changes",
                     "telemetry_visible", "synthetic_request_used", "synthetic_request_approved")
CLASS_RANK = {"incident": 0, "needs-investigation": 1, "pending": 2, "expected": 3}
STATE_RANK = {"firing": 0, "pending": 1, "inactive": 2}

TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})")
HEX_ID = re.compile(r"[0-9a-f]{32}")
INCIDENT_ID = re.compile(r"\d{4}-\d{2}-\d{2}-\d{1,3}")
SENSITIVE = re.compile(
    r"password|passwd|secret|token|api[_-]?key|bearer\s|authorization\s*:|private key|"
    r"-----BEGIN|://[^/\s:@]+:[^/\s@]+@|resume_text|job_description|request_body",
    re.IGNORECASE)

AGENT_NAME = "careerpilot-oncall-investigator (deterministic, read-only)"
AGENT_ACTIONS = "None. This agent only reads the evidence file and produces a report."


class InputError(ValueError):
    """The evidence file was rejected. Messages name fields, never input values."""


# --- validation -------------------------------------------------------------

def _keys(obj, path, required=(), optional=()):
    if not isinstance(obj, dict):
        raise InputError(f"{path} must be an object")
    missing = [key for key in required if key not in obj]
    if missing:
        raise InputError(f"{path} is missing {', '.join(missing)}")
    unknown = sorted(set(obj) - set(required) - set(optional))
    if unknown:
        raise InputError(f"{path} has unsupported field(s): {', '.join(unknown)}")


def _timestamp(value, path):
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise InputError(f"{path} must be an ISO 8601 timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InputError(f"{path} is not a valid date and time") from None
    return parsed.astimezone(timezone.utc)


def _text(value, path):
    if (not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT
            or not value.isprintable()):
        raise InputError(f"{path} must be single-line text of 1 to {MAX_TEXT} characters")
    if SENSITIVE.search(value):
        raise InputError(f"{path} looks like it contains a secret or raw content")
    return value.strip()


def _choice(value, path, options):
    if value not in options:
        raise InputError(f"{path} must be one of: {', '.join(options)}")
    return value


def _flag(value, path):
    if value is not None and not isinstance(value, bool):
        raise InputError(f"{path} must be true, false, or null")
    return value


def _items(value, path):
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise InputError(f"{path} must be a list of at most {MAX_ITEMS} items")
    return value


def _ids(value, path):
    ids = _items(value, path)
    if not all(isinstance(i, str) and HEX_ID.fullmatch(i) for i in ids):
        raise InputError(f"{path} must contain 32-character lowercase hex IDs")
    return list(ids)


def parse_evidence(data):
    """Validate the evidence document and return a normalized copy."""
    _keys(data, "input", required=("schema_version", "synthetic", "alerts"),
          optional=("incident_id", "evidence"))
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise InputError(f"input.schema_version must be {SCHEMA_VERSION}")
    if data["synthetic"] is not True:
        raise InputError("input.synthetic must be true: only synthetic evidence is accepted")
    incident_id = data.get("incident_id", "unassigned")
    if incident_id != "unassigned" and not (isinstance(incident_id, str)
                                            and INCIDENT_ID.fullmatch(incident_id)):
        raise InputError("input.incident_id must look like YYYY-MM-DD-n")

    alerts = []
    for i, raw in enumerate(_items(data["alerts"], "input.alerts")):
        path = f"alerts[{i}]"
        _keys(raw, path, required=("alertname", "state", "active_at"),
              optional=("resolved_at", "severity"))
        name = raw["alertname"]
        if not isinstance(name, str) or name not in ALERTS:
            raise InputError(f"{path}.alertname is not a CareerPilot alert")
        if any(a["alertname"] == name for a in alerts):
            raise InputError(f"{path}.alertname is listed more than once")
        if "severity" in raw and raw["severity"] != ALERTS[name]["severity"]:
            raise InputError(f"{path}.severity does not match the documented severity")
        state = _choice(raw["state"], f"{path}.state", STATES)
        active = _timestamp(raw["active_at"], f"{path}.active_at")
        resolved = None
        if "resolved_at" in raw:
            if state != "inactive":
                raise InputError(f"{path}.resolved_at is only allowed for inactive alerts")
            resolved = _timestamp(raw["resolved_at"], f"{path}.resolved_at")
            if resolved < active:
                raise InputError(f"{path}.resolved_at is before active_at")
        alerts.append({"alertname": name, "state": state, "active_at": active,
                       "resolved_at": resolved})
    if not alerts:
        raise InputError("input.alerts must contain at least one alert")

    raw = data.get("evidence", {})
    _keys(raw, "evidence", optional=("otlp_export", "impact", "observations", "root_cause",
                                     "actions", "verification") + FLAGS)
    evidence = {"otlp_export": _choice(raw.get("otlp_export", "unknown"),
                                       "evidence.otlp_export", OTLP_STATES)}
    for flag in FLAGS:
        evidence[flag] = _flag(raw.get(flag), f"evidence.{flag}")
    evidence["impact"] = _text(raw["impact"], "evidence.impact") if "impact" in raw else None

    evidence["observations"] = []
    for i, obs in enumerate(_items(raw.get("observations", []), "evidence.observations")):
        path = f"evidence.observations[{i}]"
        _keys(obs, path, required=("time", "source", "summary"),
              optional=("request_ids", "trace_ids"))
        evidence["observations"].append({
            "time": _timestamp(obs["time"], f"{path}.time"),
            "source": _choice(obs["source"], f"{path}.source", SOURCES),
            "summary": _text(obs["summary"], f"{path}.summary"),
            "request_ids": _ids(obs.get("request_ids", []), f"{path}.request_ids"),
            "trace_ids": _ids(obs.get("trace_ids", []), f"{path}.trace_ids"),
        })

    evidence["root_cause"] = None
    if "root_cause" in raw:
        cause = raw["root_cause"]
        _keys(cause, "evidence.root_cause", required=("established",), optional=("summary",))
        if not isinstance(cause["established"], bool):
            raise InputError("evidence.root_cause.established must be true or false")
        if cause["established"]:
            if "summary" not in cause:
                raise InputError("evidence.root_cause.summary is required when established")
            evidence["root_cause"] = _text(cause["summary"], "evidence.root_cause.summary")

    evidence["actions"] = []
    for i, act in enumerate(_items(raw.get("actions", []), "evidence.actions")):
        path = f"evidence.actions[{i}]"
        _keys(act, path, required=("time", "action", "approval"))
        evidence["actions"].append({
            "time": _timestamp(act["time"], f"{path}.time"),
            "action": _text(act["action"], f"{path}.action"),
            "approval": _choice(act["approval"], f"{path}.approval", APPROVALS),
        })

    checks = raw.get("verification", {})
    _keys(checks, "evidence.verification", optional=VERIFICATION_KEYS)
    evidence["verification"] = {key: _flag(checks.get(key), f"evidence.verification.{key}")
                                for key in VERIFICATION_KEYS}

    return {"incident_id": incident_id, "alerts": alerts, "evidence": evidence}


# --- analysis ---------------------------------------------------------------

def classify(alert, alerts, evidence):
    """Return (classification, note) for one alert, following the runbook."""
    if alert["state"] == "pending":
        return "pending", "Not firing yet; its `for` duration has not elapsed."
    if alert["alertname"] != TELEMETRY:
        return "incident", None
    collector = next((a for a in alerts if a["alertname"] == COLLECTOR), None)
    if (collector and collector["state"] != "inactive") or evidence["collector_up"] is False:
        return "incident", "A Collector outage is present; investigate the Collector first (runbook 5.4)."
    reasons = []
    if evidence["otlp_export"] == "disabled":
        reasons.append("OTLP export is disabled")
    if evidence["backend_running"] is False:
        reasons.append("the backend is not running")
    if evidence["backend_served_requests"] is False:
        reasons.append("the backend has not served a request since starting")
    if reasons:
        return "expected", "Expected: " + "; ".join(reasons) + "."
    if evidence["backend_in_docker"] is True:
        return ("needs-investigation", "The backend runs in Docker; the runbook marks its "
                "OTLP networking as unverified.")
    return ("needs-investigation", "No evidence establishes that missing telemetry is "
            "expected (runbook section 6).")


def verify(classification, alerts, evidence):
    """Return (status, missing checks) following runbook section 8."""
    if classification == "expected":
        return "not-applicable", []
    v = evidence["verification"]
    missing = []
    if v["alert_inactive"] is not True:
        missing.append("triggering alert shown inactive")
    elif any(a["state"] != "inactive" and a["classification"] != "expected" for a in alerts):
        missing.append("evidence still lists active alerts")
    if v["incident_check_passed"] is not True:
        missing.append("incident-specific check (runbook 8.2)")
    if v["no_unapproved_changes"] is not True:
        missing.append("no unapproved database, volume, or Render changes")
    if evidence["otlp_export"] != "disabled" and v["telemetry_visible"] is not True:
        missing.append("recent requests visible in metrics, logs, and traces")
    if v["synthetic_request_used"] is True and v["synthetic_request_approved"] is not True:
        missing.append("developer approval for the synthetic request")
    return ("verified" if not missing else "not-verified"), missing


def _utc(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def investigate(parsed):
    """Build the incident report from validated evidence."""
    evidence, alerts = parsed["evidence"], [dict(a) for a in parsed["alerts"]]
    for alert in alerts:
        alert["classification"], alert["note"] = classify(alert, alerts, evidence)
    order = list(ALERTS)
    alerts.sort(key=lambda a: (CLASS_RANK[a["classification"]], STATE_RANK[a["state"]],
                               order.index(a["alertname"])))
    primary = alerts[0]
    classification = primary["classification"]
    verification, missing = verify(classification, alerts, evidence)
    if classification == "expected":
        status = "expected-behavior"
    else:
        status = "resolved" if verification == "verified" else "open"

    events = []
    for a in alerts:
        events.append((a["active_at"], f"{a['alertname']} became active (now {a['state']})"))
        if a["resolved_at"]:
            events.append((a["resolved_at"], f"{a['alertname']} reported inactive"))
    events += [(o["time"], f"{o['source']}: {o['summary']}") for o in evidence["observations"]]
    events += [(x["time"], f"action ({x['approval']}): {x['action']}") for x in evidence["actions"]]
    events.sort(key=lambda event: event[0])

    follow_ups = []
    for a in alerts:
        if a["classification"] == "pending":
            follow_ups.append(f"Re-check {a['alertname']} after its `for` duration.")
        elif a["classification"] != "expected":
            follow_ups.append(f"Follow runbook section {ALERTS[a['alertname']]['runbook']} "
                              f"for {a['alertname']}.")
    names = {a["alertname"] for a in alerts}
    if COLLECTOR in names and TELEMETRY in names:
        follow_ups.append(f"Re-check {TELEMETRY} after the Collector recovers.")
    if evidence["otlp_export"] == "disabled" and any(
            a["alertname"] in OTLP_METRIC_ALERTS and a["state"] != "inactive" for a in alerts):
        follow_ups.append("Evidence is inconsistent: an active alert needs OTLP metrics, "
                          "but OTLP export is recorded as disabled.")
    if classification == "expected":
        follow_ups.append("No incident record is needed for expected missing telemetry "
                          "(runbook section 10).")
    elif evidence["root_cause"] is None:
        follow_ups.append("Establish the root cause; the evidence does not establish it.")
    if missing:
        follow_ups.append("Complete recovery verification (runbook section 8): "
                          + "; ".join(missing) + ".")
    follow_ups.append("Developer review and approval are required before any restart "
                      "or remediation.")

    return {
        "incident_id": parsed["incident_id"],
        "synthetic": True,
        "generated_by": AGENT_NAME,
        "alert": primary["alertname"],
        "severity": ALERTS[primary["alertname"]]["severity"],
        "classification": classification,
        "status": status,
        "active_utc": _utc(primary["active_at"]),
        "resolved_utc": _utc(primary["resolved_at"]) if status == "resolved" else None,
        "alerts": [{
            "alertname": a["alertname"],
            "severity": ALERTS[a["alertname"]]["severity"],
            "state": a["state"],
            "classification": a["classification"],
            "note": a["note"],
            "runbook_section": ALERTS[a["alertname"]]["runbook"],
            "active_utc": _utc(a["active_at"]),
            "resolved_utc": _utc(a["resolved_at"]),
        } for a in alerts],
        "impact": evidence["impact"] or "Not established from the evidence.",
        "timeline": [{"time_utc": _utc(t), "event": e} for t, e in events],
        "evidence_summary": {
            "otlp_export": evidence["otlp_export"],
            **{flag: evidence[flag] for flag in FLAGS},
            "observations": [{
                "time_utc": _utc(o["time"]), "source": o["source"], "summary": o["summary"],
                "request_ids": o["request_ids"], "trace_ids": o["trace_ids"],
            } for o in evidence["observations"]],
        },
        "root_cause": evidence["root_cause"] or "unknown",
        "actions_taken": {
            "agent": AGENT_ACTIONS,
            "recorded": [{"time_utc": _utc(x["time"]), "action": x["action"],
                          "approval": x["approval"]} for x in evidence["actions"]],
        },
        "verification": {"status": verification, "missing": missing},
        "follow_ups": follow_ups,
        "developer_review_required": True,
    }


# --- output -----------------------------------------------------------------

def render_markdown(report):
    """Render the report in the runbook's incident template layout."""
    lines = [
        f"## Incident {report['incident_id']}",
        "",
        "_Synthetic evidence. Generated by " + report["generated_by"]
        + "; developer review required._",
        "",
        f"- **Alert:** {report['alert']}",
        f"- **Severity:** {report['severity']}",
        f"- **Classification:** {report['classification']}",
        f"- **Status:** {report['status']}",
        f"- **Active (UTC):** {report['active_utc']}",
        f"- **Resolved (UTC):** {report['resolved_utc'] or 'not verified'}",
        f"- **Responder:** {report['generated_by']}, with developer review",
        "",
        "### Alerts (investigation order)",
        "",
    ]
    for a in report["alerts"]:
        note = f" {a['note']}" if a["note"] else ""
        lines.append(f"- {a['alertname']} ({a['severity']}, {a['state']}): "
                     f"{a['classification']}; runbook {a['runbook_section']}.{note}")
    lines += ["", "### Impact", "", report["impact"], "", "### Timeline (UTC)", ""]
    lines += [f"- {t['time_utc']} - {t['event']}" for t in report["timeline"]] or ["- none"]
    summary = report["evidence_summary"]
    lines += ["", "### Evidence", ""]
    lines += [f"- {key}: {json.dumps(summary[key])}" for key in ("otlp_export",) + FLAGS]
    for o in summary["observations"]:
        ids = o["request_ids"] + o["trace_ids"]
        lines.append(f"- {o['time_utc']} {o['source']}: {o['summary']}"
                     + (f" (IDs: {', '.join(ids)})" if ids else ""))
    lines += ["", "### Root Cause", "", report["root_cause"], "", "### Actions Taken", "",
              f"- Agent: {report['actions_taken']['agent']}"]
    lines += [f"- {x['time_utc']} - {x['action']} - {x['approval']}"
              for x in report["actions_taken"]["recorded"]]
    verification = report["verification"]
    lines += ["", "### Verification", "", f"- Status: {verification['status']}"]
    lines += [f"- [ ] {item}" for item in verification["missing"]]
    lines += ["", "### Follow-ups", ""] + [f"- {item}" for item in report["follow_ups"]]
    return "\n".join(lines) + "\n"


def load_evidence(path):
    path = Path(path)
    if not path.is_file():
        raise InputError("the evidence file does not exist")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise InputError(f"the evidence file is larger than {MAX_INPUT_BYTES} bytes")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InputError("the evidence file is not valid UTF-8 JSON") from None
    return parse_evidence(data)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CareerPilot on-call investigator (synthetic evidence, read-only).")
    parser.add_argument("evidence", help="Local JSON evidence file to read.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument("--output", help="Write the report to this NEW file instead of stdout.")
    args = parser.parse_args(argv)

    try:
        report = investigate(load_evidence(args.evidence))
    except InputError as exc:
        print(f"oncall investigator: rejected input: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(report, indent=2) + "\n" if args.json else render_markdown(report)
    if not args.output:
        sys.stdout.write(text)
        return 0
    output = Path(args.output)
    if output.resolve() == Path(args.evidence).resolve():
        print("oncall investigator: refusing to overwrite the evidence file", file=sys.stderr)
        return 2
    try:
        with output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError:
        print("oncall investigator: refusing to overwrite an existing file", file=sys.stderr)
        return 2
    except OSError:
        print("oncall investigator: could not create the output file", file=sys.stderr)
        return 2
    print(f"report written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
