"""CT Boot Observer — minimal, import-safe boot sentinel.

Run in modes where CT needs to verify boot invariants and record a
single canonical READY file and an append-only audit event.

This module is import-safe (no actions at import time). Use `main()` to
execute behavior. Paths and probe behavior are overridable for tests.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any

# Defaults — tests may override these module attributes
READY_PATH: Path = Path("/run/dam-os/READY")
AUDIT_PATH: Path = Path(os.path.expanduser("~/.mad_os/AUDIT.log"))
SWEEP: Path = Path("/usr/local/bin/system_snag_sweep.sh")

ALLOWED = {"READY", "DEGRADED", "HALT"}


def sha256(s: bytes) -> str:
    return hashlib.sha256(s).hexdigest()


def run_sweep() -> Dict[str, Any]:
    if not SWEEP.exists():
        return {"ok": False, "error": "snag_sweep_missing"}
    p = subprocess.run([str(SWEEP)], capture_output=True, text=True)
    return {"ok": p.returncode == 0, "rc": p.returncode, "stdout": p.stdout[-8000:], "stderr": p.stderr[-8000:]}


def invariants() -> Dict[str, bool]:
    checks = {
        "network": os.system("getent hosts google.com >/dev/null 2>&1") == 0,
        "docker": os.system("systemctl is-active docker >/dev/null 2>&1") == 0,
        "disk_rw": os.access("/", os.W_OK),
        "authority_lock": Path("/srv/ct/ct_lock.json").exists(),
    }
    return checks


def verdict(checks: Dict[str, bool]) -> str:
    # Conservative: if any critical check fails, HALT
    if not all(checks.values()):
        return "HALT"
    return "READY"


def write_ready(status: str, note: str):
    assert status in ALLOWED
    READY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": status, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verifier": "ct.boot_observer", "note": note}
    data = json.dumps(payload, sort_keys=True).encode()
    READY_PATH.write_bytes(data)
    try:
        os.chmod(READY_PATH, 0o640)
    except Exception:
        # best-effort on chmod
        pass


def audit(event: Dict[str, Any]):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True).encode()
    with open(AUDIT_PATH, "ab") as f:
        f.write(line + b"\n")
        f.write(f"# sha256={sha256(line)}\n".encode())


def main(dry_run: bool = False) -> None:
    sweep = run_sweep()
    checks = invariants()
    status = verdict(checks)
    event = {"action": "boot.sweep", "status": status, "checks": checks, "sweep_ok": sweep.get("ok"), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    audit(event)
    if not dry_run:
        write_ready(status, "boot observer completed")
    if status == "HALT":
        raise SystemExit(1)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
