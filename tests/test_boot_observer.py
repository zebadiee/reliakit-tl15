import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ct_runtime import boot_observer


def make_sweep_script(path: Path, rc: int = 0, out: str = "ok"):
    content = f"#!/usr/bin/env bash\necho '{out}'\nexit {rc}\n"
    path.write_text(content)
    path.chmod(0o755)


def test_boot_observer_dry_run_records_audit(tmp_path: Path):
    # override module paths
    audit = tmp_path / "audit.log"
    boot_observer.AUDIT_PATH = audit

    sweep = tmp_path / "sweep.sh"
    make_sweep_script(sweep, rc=0, out="ok")
    boot_observer.SWEEP = sweep

    # run dry-run: should write audit but not READY
    boot_observer.READY_PATH = tmp_path / "READY"
    if boot_observer.READY_PATH.exists():
        boot_observer.READY_PATH.unlink()

    boot_observer.main(dry_run=True)
    assert audit.exists()
    lines = audit.read_text().splitlines()
    assert len(lines) >= 2  # JSON line + sha line
    entry = json.loads(lines[-2])
    assert entry["action"] == "boot.sweep"


def test_boot_observer_halt_on_missing_invariant(tmp_path: Path):
    audit = tmp_path / "audit2.log"
    boot_observer.AUDIT_PATH = audit
    sweep = tmp_path / "sweep2.sh"
    make_sweep_script(sweep, rc=0, out="ok")
    boot_observer.SWEEP = sweep

    boot_observer.READY_PATH = tmp_path / "READY2"

    # monkeypatch invariants to simulate missing docker
    orig_invariants = boot_observer.invariants

    def bad_invariants():
        d = orig_invariants()
        d["docker"] = False
        return d

    boot_observer.invariants = bad_invariants
    with pytest.raises(SystemExit):
        boot_observer.main(dry_run=False)

    # audit entry exists and last status is HALT
    lines = audit.read_text().splitlines()
    assert len(lines) >= 2
    entry = json.loads(lines[-2])
    assert entry["status"] == "HALT"
    # restore
    boot_observer.invariants = orig_invariants
