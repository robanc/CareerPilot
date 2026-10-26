"""Disposable synthetic sandbox for the CareerPilot on-call responder.

A sandbox is a new temporary directory that stands in for a service. It holds
a marker file, a synthetic service config (with a fault switch), a known-good
copy of that config, and a spool directory for synthetic alert events. The
SyntheticService answers simulated requests from the config alone: no
sockets, no real CareerPilot code, no database, no Docker.

Used by oncall_responder.py (--demo) and by its tests. Nothing here touches
anything outside the sandbox it created.
"""

import json
import re
import secrets
import shutil
import tempfile
from pathlib import Path

MARKER_NAME = ".careerpilot-synthetic-sandbox"
CONFIG_NAME = "service-config.json"
KNOWN_GOOD_NAME = "known-good-config.json"
PERSISTENT_FAULT_NAME = "persistent-fault"
SPOOL_NAME = "alerts"
AUDIT_NAME = "audit.jsonl"
CREATED_BY = "careerpilot-oncall-responder"
KNOWN_GOOD = {"service": "careerpilot-synthetic", "fault_5xx": False}
EVENT_SOURCE = "synthetic-alert-spool"


def _dump(obj):
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def create_sandbox(parent=None):
    """Create a new marked sandbox under the system temp directory."""
    root = Path(tempfile.mkdtemp(prefix="careerpilot-oncall-", dir=parent)).resolve()
    (root / MARKER_NAME).write_bytes(_dump({"created_by": CREATED_BY, "synthetic": True,
                                            "nonce": secrets.token_hex(16)}))
    (root / KNOWN_GOOD_NAME).write_bytes(_dump(KNOWN_GOOD))
    (root / CONFIG_NAME).write_bytes(_dump(KNOWN_GOOD))
    (root / SPOOL_NAME).mkdir()
    return root


def is_valid_marker(path):
    """True only for a marker file written by create_sandbox."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (isinstance(data, dict) and set(data) == {"created_by", "synthetic", "nonce"}
            and data["created_by"] == CREATED_BY and data["synthetic"] is True
            and isinstance(data["nonce"], str)
            and re.fullmatch(r"[0-9a-f]{32}", data["nonce"]) is not None)


def inject_fault(root, persistent=False):
    """Turn on the synthetic 5xx fault.

    persistent=True adds a second fault outside the config, which the
    allowlisted repair cannot clear (used to exercise rollback).
    """
    root = Path(root)
    config = json.loads((root / CONFIG_NAME).read_text(encoding="utf-8"))
    config["fault_5xx"] = True
    (root / CONFIG_NAME).write_bytes(_dump(config))
    if persistent:
        (root / PERSISTENT_FAULT_NAME).write_text("synthetic\n", encoding="utf-8")


def write_alert_event(root, alertname, severity, starts_at, *, state="firing",
                      fingerprint=None, name=None):
    """Drop one synthetic alert event into the spool; returns (path, fingerprint)."""
    fingerprint = fingerprint or secrets.token_hex(8)
    event = {"schema_version": 1, "synthetic": True, "source": EVENT_SOURCE,
             "alertname": alertname, "severity": severity, "state": state,
             "starts_at": starts_at, "fingerprint": fingerprint}
    path = Path(root) / SPOOL_NAME / (name or f"{fingerprint}.json")
    path.write_bytes(_dump(event))
    return path, fingerprint


class SyntheticService:
    """Answers simulated requests: 500 while a fault is active, else 200."""

    def __init__(self, config_path, persistent_fault_path):
        self.config_path = Path(config_path)
        self.persistent_fault_path = Path(persistent_fault_path)

    def handle_request(self):
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return 500
        if not isinstance(config, dict) or config.get("fault_5xx") is not False:
            return 500
        return 500 if self.persistent_fault_path.exists() else 200


def remove_sandbox(root):
    """Delete a sandbox, refusing anything that is not a marked temp sandbox."""
    root = Path(root)
    temp = Path(tempfile.gettempdir()).resolve()
    if (root.is_symlink() or not root.is_dir() or temp not in root.resolve().parents
            or not is_valid_marker(root / MARKER_NAME)):
        raise ValueError("refusing to remove a directory that is not a synthetic sandbox")
    shutil.rmtree(root)
