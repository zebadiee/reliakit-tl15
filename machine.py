#!/usr/bin/env python3
"""
ct-machine — read-only observer for Hermes (MACHINE v1)
- Enforces startup asserts (CT_NODE_ID, CT_MODE, CT_ROLE)
- Reads from local SQLite DB and Atlas files only
- Emits deterministic narration to stdout
- Writes a single JSON state file to /run/ct/machine.state (overwrites)
- Exits on invariant violations or critical errors
"""
from __future__ import annotations
import os
import sys
import time
import json
import sqlite3
import glob
import hashlib
from datetime import datetime, timezone

# --- Startup invariants (fail-fast) ---
if os.environ.get("CT_NODE_ID") != "HERMES":
    print("CRITICAL: AUTHORITY VIOLATION (CT_NODE_ID)", file=sys.stderr)
    sys.exit(2)
if os.environ.get("CT_MODE") != "LOCKED":
    print("CRITICAL: SYSTEM NOT LOCKED", file=sys.stderr)
    sys.exit(2)
if os.environ.get("CT_ROLE") == "admin":
    print("CRITICAL: CT_ROLE must NOT be 'admin' for MACHINE", file=sys.stderr)
    sys.exit(2)

# --- Configuration ---
DATA_DIR = os.environ.get("CT_DATA", os.path.expanduser("~/invictus/data"))
DB_PATH = os.path.join(DATA_DIR, "ct_memory.db")
ATLAS_PATHS = ["/srv/ct/atlas", "/home/zebadiee/ct-runtime/ATLAS_lock"]
STATE_PATH = "/run/ct/machine.state"
CT_VERSION = os.environ.get("CT_VERSION", "unknown")
CT_CONTRACT_TAG = os.environ.get("CT_CONTRACT_TAG", "unknown")
CT_SNAPSHOT_ID = os.environ.get("CT_SNAPSHOT_ID")
POLL_INTERVAL = int(os.environ.get("CT_MACHINE_POLL", "30"))

# --- Helpers ---

def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def read_db_summary(db_path: str):
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Agents
    cur.execute("SELECT agent_id, role, status, last_seen FROM agents")
    agents = [dict(agent_id=r[0], role=r[1], status=r[2], last_seen=r[3]) for r in cur.fetchall()]
    # Task summary (exo_jobs)
    cur.execute("SELECT status, COUNT(*) FROM exo_jobs GROUP BY status")
    tasks = {r[0]: r[1] for r in cur.fetchall()}
    # Node identity
    try:
        cur.execute("SELECT node_id, role, locked FROM node_identity LIMIT 1")
        row = cur.fetchone()
        node = dict(node_id=row[0], role=row[1], locked=bool(row[2])) if row else {}
    except Exception:
        node = {}
    conn.close()
    return {"agents": agents, "tasks": tasks, "node": node}


def verify_ledger(paths: list[str]):
    results = {"present": False, "files": {}}
    found = False
    for base in paths:
        ev = os.path.join(base, "events")
        dec = os.path.join(base, "decisions")
        af = os.path.join(base, "audit_flags")
        for p in (ev, dec, af):
            if not os.path.isdir(p):
                continue
            found = True
            for f in sorted(glob.glob(os.path.join(p, "*.jsonl"))):
                cnt = 0
                ok = True
                h = hashlib.sha256()
                try:
                    with open(f, "rb") as fh:
                        for line in fh:
                            cnt += 1
                            # validate JSON
                            try:
                                json.loads(line.decode("utf-8"))
                            except Exception:
                                ok = False
                                break
                            h.update(line.rstrip(b"\n"))
                except Exception:
                    ok = False
                results["files"][f] = {"lines": cnt, "ok": ok, "sha256": h.hexdigest()}
    results["present"] = found
    return results


def write_state(state: dict):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
        os.replace(tmp, STATE_PATH)
    except Exception as e:
        print(f"ERROR: failed to write state: {e}", file=sys.stderr)
        raise


def narrate(state: dict):
    # Deterministic, concise narration
    ts = state.get("timestamp")
    agents = state.get("db_summary", {}).get("agents", [])
    online = sum(1 for a in agents if a.get("status") == "ONLINE")
    stale = sum(1 for a in agents if a.get("status") == "STALE")
    tasks = state.get("db_summary", {}).get("tasks", {})
    task_summary = ", ".join([f"{k}:{v}" for k, v in sorted(tasks.items())]) or "none"
    ledger_ok = all(f.get("ok") for f in state.get("ledger", {}).get("files", {}).values()) if state.get("ledger", {}).get("files") else False
    risk = "NONE" if ledger_ok and stale == 0 else "FOR REVIEW"
    lines = []
    lines.append(f"{ts} — MACHINE OBSERVATION")
    lines.append(f"Agents online: {online}; stale: {stale}")
    lines.append(f"Tasks: {task_summary}")
    lines.append(f"Ledger OK: {ledger_ok}; Risk: {risk}")
    print("\n".join(lines))


# --- Main loop ---

def run_once():
    timestamp = utcnow_iso()
    db_summary = read_db_summary(DB_PATH)
    ledger = verify_ledger(ATLAS_PATHS)
    state = {
        "timestamp": timestamp,
        "ct_version": CT_VERSION,
        "ct_contract_tag": CT_CONTRACT_TAG,
        "ct_snapshot_id": CT_SNAPSHOT_ID,
        "db_summary": db_summary,
        "ledger": ledger,
    }
    write_state(state)
    narrate(state)


if __name__ == "__main__":
    try:
        # single-run first, then loop
        run_once()
    except FileNotFoundError as e:
        print(f"CRITICAL: missing resource: {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"ERROR: unexpected failure: {e}", file=sys.stderr)
        sys.exit(4)

    # Run periodically in silent observe mode
    try:
        while True:
            time.sleep(POLL_INTERVAL)
            run_once()
    except KeyboardInterrupt:
        print("INFO: exiting by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(5)
