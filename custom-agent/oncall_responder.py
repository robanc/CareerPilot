"""CareerPilot on-call responder: a synthetic-only, alert-activated repair agent.

A deterministic agent (no LLM). It wakes when a synthetic alert event appears
in the spool of a disposable synthetic sandbox (synthetic_sandbox.py). For
CareerPilotHigh5xxRate only, it applies ONE allowlisted, reversible repair to
that sandbox, verifies it against the documented alert thresholds, and rolls
back if verification fails. Every step goes to a privacy-safe JSON Lines audit
log, and oncall_investigator.py produces the incident report.

It never touches the real CareerPilot application, any database, Docker, the
monitoring stack, Render, or the network, and it refuses any directory that is
not a marked synthetic sandbox. Real-service remediation still requires
developer approval (monitoring/INCIDENT_RESPONSE.md).

Rules:
  wake         one spool scan with --once; at most --max-cycles scans with --watch
  events       strict schema, "synthetic": true, one of the four CareerPilot
               alerts with its documented severity, not in the future
  allowlist    only CareerPilotHigh5xxRate has a repair: restore the sandbox's
               known-good service config. The other alerts are report-only.
  sandbox      must carry the marker file, sit inside the system temp directory
               and outside the repository, and contain no symlinks
  confirm      the repair runs only if the 5xx condition is observed first
  backup       the config bytes are saved, and checked by SHA-256, before the repair
  verify       the alert rule's thresholds: 5xx ratio at most 0.05 over at least
               10 synthetic requests
  rollback     on failed verification the backup is restored and checked by hash
  duplicates   each alert fingerprint is acted on at most once
  audit        steps, hashes, counts, and outcomes only; never file contents,
               paths, or event payloads

Usage, from the repository root:
    python custom-agent/oncall_responder.py --demo
    python custom-agent/oncall_responder.py --sandbox DIR --once
    python custom-agent/oncall_responder.py --sandbox DIR --watch [--interval S] [--max-cycles N]
Exit code 0 when no processed incident is left open, 1 when one is,
2 when the sandbox or the arguments are refused.
"""

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oncall_investigator as oi
import synthetic_sandbox as sb

ROOT = Path(__file__).resolve().parents[1]

# Thresholds of CareerPilotHigh5xxRate in monitoring/alerts/careerpilot.rules.yml.
RATIO_THRESHOLD = 0.05
MIN_REQUESTS = 10
VERIFY_REQUESTS = 20

REPAIRS = {"CareerPilotHigh5xxRate": "restore_known_good_config"}
APPROVAL = "automated-synthetic-repair"

EVENT_KEYS = {"schema_version", "synthetic", "source", "alertname", "severity", "state",
              "starts_at", "fingerprint"}
EVENT_STATES = ("pending", "firing")
EVENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.json")
FINGERPRINT = re.compile(r"[0-9a-f]{16}")
MAX_EVENT_BYTES = 16 * 1024
MAX_INTERVAL = 60
MAX_CYCLES = 100
AUDIT_FIELDS = {"fingerprint", "alertname", "event_sha256", "reason", "action", "outcome",
                "requests", "errors_5xx", "ratio", "config_sha256_before",
                "config_sha256_after", "backup_sha256", "status"}


class SandboxError(RuntimeError):
    """The directory is not a safe synthetic sandbox; nothing was changed."""


class EventError(ValueError):
    """A spool event was rejected. Messages name fields, never values."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _utc(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now():
    return datetime.now(timezone.utc)


def alert_condition(requests, errors):
    """The alert rule: more than 5% 5xx, with at least 10 requests."""
    return requests >= MIN_REQUESTS and errors / requests > RATIO_THRESHOLD


def verification_passed(requests, errors):
    return requests >= MIN_REQUESTS and errors / requests <= RATIO_THRESHOLD


class Sandbox:
    """A verified synthetic sandbox. Construction refuses anything else."""

    def __init__(self, path):
        root = Path(path)
        if root.is_symlink() or not root.is_dir():
            raise SandboxError("the sandbox must be an existing directory, not a symlink")
        resolved = root.resolve()
        temp = Path(tempfile.gettempdir()).resolve()
        if temp not in resolved.parents:
            raise SandboxError("the sandbox must be inside the system temp directory")
        if resolved == ROOT or ROOT in resolved.parents:
            raise SandboxError("the sandbox must be outside the repository")
        self.root = resolved
        if not sb.is_valid_marker(self.path(sb.MARKER_NAME)):
            raise SandboxError("the directory is not a marked synthetic sandbox")
        spool = self.path(sb.SPOOL_NAME)
        if not spool.is_dir():
            raise SandboxError("the sandbox has no alert spool")

    def path(self, name):
        """A sandbox entry by fixed name; refuses symlinks and escapes."""
        candidate = self.root / name
        if candidate.is_symlink() or candidate.is_junction():
            raise SandboxError(f"sandbox entry {name} is a symlink")
        if candidate.exists() and candidate.resolve().parent != self.root:
            raise SandboxError(f"sandbox entry {name} resolves outside the sandbox")
        return candidate

    def write_atomic(self, name, data):
        temporary = self.path(name + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(self.path(name))


class Audit:
    """Append-only JSON Lines audit log inside the sandbox."""

    def __init__(self, sandbox, clock):
        self.sandbox = sandbox
        self.clock = clock
        self.entries = self._load()

    def _load(self):
        file = self.sandbox.path(sb.AUDIT_NAME)
        if not file.exists():
            return []
        try:
            return [json.loads(line) for line in
                    file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SandboxError("the sandbox audit log is not valid JSON Lines") from None

    def record(self, step, **fields):
        unknown = set(fields) - AUDIT_FIELDS
        if unknown:
            raise ValueError(f"audit field(s) not allowed: {', '.join(sorted(unknown))}")
        entry = {"seq": len(self.entries) + 1, "time_utc": _utc(self.clock()), "step": step,
                 **fields}
        self.entries.append(entry)
        with self.sandbox.path(sb.AUDIT_NAME).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def seen_events(self):
        return {e["event_sha256"] for e in self.entries if "event_sha256" in e}

    def handled_fingerprints(self):
        return {e["fingerprint"] for e in self.entries if e["step"] == "woke"}


def validate_event(event, now):
    if not isinstance(event, dict) or set(event) != EVENT_KEYS:
        raise EventError("the event must have exactly the documented fields")
    if type(event["schema_version"]) is not int or event["schema_version"] != 1:
        raise EventError("schema_version must be 1")
    if event["synthetic"] is not True or event["source"] != sb.EVENT_SOURCE:
        raise EventError("only synthetic spool events are accepted")
    name = event["alertname"]
    if not isinstance(name, str) or name not in oi.ALERTS:
        raise EventError("alertname is not a CareerPilot alert")
    if event["severity"] != oi.ALERTS[name]["severity"]:
        raise EventError("severity does not match the documented severity")
    if event["state"] not in EVENT_STATES:
        raise EventError("state must be pending or firing")
    try:
        starts = oi._timestamp(event["starts_at"], "starts_at")
    except oi.InputError:
        raise EventError("starts_at must be an ISO 8601 timestamp with a timezone") from None
    if starts > now:
        raise EventError("starts_at is in the future")
    if not isinstance(event["fingerprint"], str) or not FINGERPRINT.fullmatch(event["fingerprint"]):
        raise EventError("fingerprint must be 16 lowercase hex characters")
    return {"alertname": name, "state": event["state"], "starts_at": starts,
            "fingerprint": event["fingerprint"]}


class Responder:
    def __init__(self, sandbox, clock=_now):
        self.sandbox = sandbox
        self.clock = clock
        self.audit = Audit(sandbox, clock)
        self.ignored = set()

    # --- wake ---------------------------------------------------------------

    def run_cycle(self):
        """Scan the spool once and handle every new event."""
        results = []
        seen, handled = self.audit.seen_events(), self.audit.handled_fingerprints()
        for entry in sorted(self.sandbox.path(sb.SPOOL_NAME).iterdir(), key=lambda p: p.name):
            if entry.name in self.ignored:
                continue
            if (entry.is_symlink() or not entry.is_file() or not EVENT_NAME.fullmatch(entry.name)
                    or entry.stat().st_size > MAX_EVENT_BYTES):
                self.ignored.add(entry.name)
                self.audit.record("event-ignored", reason="not a regular, bounded .json spool file")
                continue
            data = entry.read_bytes()
            digest = sha256(data)
            if digest in seen:
                continue
            seen.add(digest)
            try:
                alert = validate_event(json.loads(data.decode("utf-8")), self.clock())
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.audit.record("event-rejected", event_sha256=digest,
                                  reason="the event is not valid UTF-8 JSON")
                continue
            except EventError as exc:
                self.audit.record("event-rejected", event_sha256=digest, reason=str(exc))
                continue
            if alert["fingerprint"] in handled:
                self.audit.record("duplicate-skipped", event_sha256=digest,
                                  fingerprint=alert["fingerprint"], alertname=alert["alertname"])
                continue
            handled.add(alert["fingerprint"])
            self.audit.record("woke", event_sha256=digest, fingerprint=alert["fingerprint"],
                              alertname=alert["alertname"])
            results.append(self.handle(alert))
        return results

    def watch(self, max_cycles, interval, sleep=time.sleep):
        results = []
        for cycle in range(max_cycles):
            results += self.run_cycle()
            if cycle < max_cycles - 1:
                sleep(interval)
        return results

    # --- respond ------------------------------------------------------------

    def handle(self, alert):
        fp, name = alert["fingerprint"], alert["alertname"]
        if alert["state"] != "firing":
            self.audit.record("not-firing", fingerprint=fp, alertname=name, outcome="report-only")
            return self._finish(alert, "not-firing")
        if name not in REPAIRS:
            self.audit.record("no-allowlisted-repair", fingerprint=fp, alertname=name,
                              outcome="report-only")
            return self._finish(alert, "report-only")

        before = self._measure()
        observed = alert_condition(*before)
        self._record_measure("condition-check", fp, before, "observed" if observed else "not-observed")
        if not observed:
            return self._finish(alert, "condition-not-observed", before=before)

        original = self._repair(fp)
        if original is None:
            return self._finish(alert, "repair-refused", before=before)

        after = self._measure()
        passed = verification_passed(*after)
        self._record_measure("verification", fp, after, "passed" if passed else "failed")
        if passed:
            return self._finish(alert, "resolved", before=before,
                                config_fault=_config_fault(original))
        self._rollback(fp, original)
        return self._finish(alert, "rolled-back", before=before)

    def _measure(self, requests=VERIFY_REQUESTS):
        service = sb.SyntheticService(self.sandbox.path(sb.CONFIG_NAME),
                                      self.sandbox.path(sb.PERSISTENT_FAULT_NAME))
        errors = sum(500 <= service.handle_request() <= 599 for _ in range(requests))
        return requests, errors

    def _record_measure(self, step, fp, measured, outcome):
        requests, errors = measured
        self.audit.record(step, fingerprint=fp, requests=requests, errors_5xx=errors,
                          ratio=round(errors / requests, 4), outcome=outcome)

    def _repair(self, fp):
        """Back up, then restore the known-good config. Returns the original bytes."""
        action = REPAIRS["CareerPilotHigh5xxRate"]
        try:
            original = self.sandbox.path(sb.CONFIG_NAME).read_bytes()
            known_good = self.sandbox.path(sb.KNOWN_GOOD_NAME).read_bytes()
        except OSError:
            self.audit.record("repair-refused", fingerprint=fp, action=action,
                              reason="the sandbox config files are missing")
            return None
        if _config_fault(known_good) is not False:
            self.audit.record("repair-refused", fingerprint=fp, action=action,
                              reason="the known-good config is not valid")
            return None
        backup = self.sandbox.path(f"config-backup-{fp}.json")
        try:
            with backup.open("xb") as handle:
                handle.write(original)
        except FileExistsError:
            self.audit.record("repair-refused", fingerprint=fp, action=action,
                              reason="a backup for this fingerprint already exists")
            return None
        if sha256(backup.read_bytes()) != sha256(original):
            self.audit.record("repair-refused", fingerprint=fp, action=action,
                              reason="the backup does not match the original")
            return None
        self.audit.record("backup-saved", fingerprint=fp, config_sha256_before=sha256(original),
                          backup_sha256=sha256(original))
        self.sandbox.write_atomic(sb.CONFIG_NAME, known_good)
        self.audit.record("repair-applied", fingerprint=fp, action=action,
                          config_sha256_before=sha256(original),
                          config_sha256_after=sha256(self.sandbox.path(sb.CONFIG_NAME).read_bytes()))
        return original

    def _rollback(self, fp, original):
        self.sandbox.write_atomic(sb.CONFIG_NAME, original)
        restored = sha256(self.sandbox.path(sb.CONFIG_NAME).read_bytes())
        self.audit.record("rolled-back", fingerprint=fp, config_sha256_after=restored,
                          outcome="restored" if restored == sha256(original) else "restore-mismatch")

    # --- report -------------------------------------------------------------

    def _finish(self, alert, outcome, before=None, config_fault=None):
        report = oi.investigate(oi.parse_evidence(
            build_evidence(alert, outcome, before, config_fault, self.clock())))
        self.audit.record("reported", fingerprint=alert["fingerprint"], outcome=outcome,
                          status=report["status"])
        return {"fingerprint": alert["fingerprint"], "alertname": alert["alertname"],
                "outcome": outcome, "report": report}


def _config_fault(data):
    """The config's fault_5xx value, or None if it is not a valid config."""
    try:
        config = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    value = config.get("fault_5xx") if isinstance(config, dict) else None
    return value if isinstance(value, bool) else None


def build_evidence(alert, outcome, before, config_fault, now):
    """Synthetic evidence for oncall_investigator.py, from what was actually checked."""
    resolved = outcome == "resolved"
    entry = {"alertname": alert["alertname"], "state": "inactive" if resolved else alert["state"],
             "active_at": _utc(alert["starts_at"])}
    if resolved:
        entry["resolved_at"] = _utc(now)
    # The sandbox exports no OTLP telemetry. "disabled" is used only once the
    # alert is resolved, so an open 5xx alert is not reported as inconsistent.
    evidence = {"otlp_export": "disabled" if resolved else "unknown"}
    if before:
        evidence["impact"] = (f"Synthetic sandbox: {before[1]} of {before[0]} synthetic "
                              "requests returned 5xx before any repair.")
    actions = []
    if outcome in ("resolved", "rolled-back"):
        actions.append({"time": _utc(now), "approval": APPROVAL, "action":
                        "Restored the known-good synthetic sandbox service config "
                        "(allowlisted repair)."})
    if outcome == "rolled-back":
        actions.append({"time": _utc(now), "approval": APPROVAL, "action":
                        "Rolled back the synthetic sandbox config after verification failed."})
    if actions:
        evidence["actions"] = actions
    if resolved:
        evidence["verification"] = {"alert_inactive": True, "incident_check_passed": True,
                                    "no_unapproved_changes": True}
        if config_fault is True:
            evidence["root_cause"] = {"established": True, "summary":
                                      "Injected synthetic fault: fault_5xx was enabled in the "
                                      "sandbox service config."}
    elif outcome == "rolled-back":
        evidence["verification"] = {"alert_inactive": False, "incident_check_passed": False,
                                    "no_unapproved_changes": True}
    return {"schema_version": 1, "synthetic": True, "alerts": [entry], "evidence": evidence}


def _print(results, as_json, audit_entries):
    if as_json:
        print(json.dumps({"synthetic": True, "results": results, "audit": audit_entries},
                         indent=2))
        return
    if not results:
        print("No new synthetic alert events.")
    for result in results:
        print(f"# Responder outcome: {result['outcome']} ({result['alertname']})\n")
        print(oi.render_markdown(result["report"]))
    print(f"Audit: {len(audit_entries)} entries in the sandbox audit log.")


def main(argv=None, clock=_now, sleep=time.sleep):
    parser = argparse.ArgumentParser(
        description="CareerPilot on-call responder (synthetic sandbox only).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Scan the spool once.")
    mode.add_argument("--watch", action="store_true", help="Poll the spool, bounded.")
    mode.add_argument("--demo", action="store_true",
                      help="Create a sandbox, inject a fault, respond, then remove it.")
    parser.add_argument("--sandbox", help="A marked synthetic sandbox directory.")
    parser.add_argument("--interval", type=int, default=5,
                        help=f"Seconds between --watch scans (1-{MAX_INTERVAL}).")
    parser.add_argument("--max-cycles", type=int, default=10,
                        help=f"Number of --watch scans (1-{MAX_CYCLES}).")
    parser.add_argument("--json", action="store_true", help="Print results as JSON.")
    args = parser.parse_args(argv)
    if not 1 <= args.interval <= MAX_INTERVAL:
        parser.error(f"--interval must be between 1 and {MAX_INTERVAL}")
    if not 1 <= args.max_cycles <= MAX_CYCLES:
        parser.error(f"--max-cycles must be between 1 and {MAX_CYCLES}")
    if args.demo == bool(args.sandbox):
        parser.error("use --sandbox with --once or --watch, or --demo without --sandbox")

    created = None
    try:
        if args.demo:
            created = sb.create_sandbox()
            sb.inject_fault(created)
            name = "CareerPilotHigh5xxRate"
            sb.write_alert_event(created, name, oi.ALERTS[name]["severity"],
                                 _utc(clock() - timedelta(minutes=5)))
        sandbox = Sandbox(created or args.sandbox)
        responder = Responder(sandbox, clock)
        if args.watch:
            results = responder.watch(args.max_cycles, args.interval, sleep)
        else:
            results = responder.run_cycle()
        _print(results, args.json, responder.audit.entries)
    except SandboxError as exc:
        print(f"oncall responder: refused: {exc}", file=sys.stderr)
        return 2
    finally:
        if created:
            sb.remove_sandbox(created)
    if args.demo and not args.json:
        print("Demo sandbox removed.")
    return 1 if any(r["report"]["status"] == "open" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
