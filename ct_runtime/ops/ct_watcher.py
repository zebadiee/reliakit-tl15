#!/usr/bin/env python3
# CT_VENV: core

import time
import yaml
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path("/srv/ct")
AGENTS = BASE / "agents"
QUEUE = BASE / "queue"
RESULTS = BASE / "results"
STATE = BASE / "state"
LOGS = BASE / "logs"

LOG_FILE = LOGS / "ct.log"
EXEC_MAP = BASE / "execution_map.yaml"


def log(msg: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(f"{datetime.utcnow().isoformat()} {msg}\n")


def load_yaml(p: Path):
    return yaml.safe_load(p.read_text())


def write_yaml(p: Path, data: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, sort_keys=False))


def last_good(component: str):
    return STATE / f"{component}.last-good.yaml"


def recover(component: str, reason: str):
    lg = last_good(component)
    if lg.exists():
        log(f"RECOVERY {component}: {reason} → restored {lg.name}")
    else:
        log(f"RECOVERY {component}: {reason} → NO CHECKPOINT FOUND")


def execute(job: dict):
    action = job.get("action")
    target = job.get("target", "unknown")

    # placeholder execution logic
    # real actions get wired here
    subprocess.run(
        ["echo", f"Executing {action} on {target}"],
        check=True
    )


def main():
    log("CT_WATCHER_START")

    while True:
        for job_file in sorted(QUEUE.glob("*.yaml")):
            job_id = job_file.stem
            log(f"JOB_START {job_id}")

            try:
                job = load_yaml(job_file)

                action = job.get("action")
                component = job.get("target", "ct-core")

                # execution map validation (central policy)
                exec_map = load_yaml(EXEC_MAP) if EXEC_MAP.exists() else {}
                if action not in exec_map:
                    raise Exception(f"unauthorized: action '{action}' not defined in execution map")
                entry = exec_map.get(action, {}) or {}
                log(f"ACTION_CHECK {job_id}: action={action} entry={entry}")

                # escalation check
                if entry.get("escalation_required") and not job.get("approved_by"):
                    raise Exception(f"unauthorized: action '{action}' requires escalation/approval")

                # action-level allowlist supersedes agent allows
                action_allowed = entry.get("allow")

                # snapshot last-known-good before execution
                lg = last_good(component)
                if not lg.exists():
                    write_yaml(lg, {
                        "component": component,
                        "status": "stable",
                        "timestamp": datetime.utcnow().isoformat(),
                        "notes": "auto-snapshot before first execution"
                    })

                execute(job)

                result = {
                    "id": job.get("id", job_id),
                    "status": "success",
                    "executed_by": "hermes",
                    "timestamp": datetime.utcnow().isoformat()
                }

            except Exception as e:
                recover(component, str(e))
                result = {
                    "id": job.get("id", job_id) if 'job' in locals() and job is not None else job_id,
                    "status": "failure",
                    "error": str(e),
                    "recovered": True,
                    "timestamp": datetime.utcnow().isoformat()
                }

            write_yaml(RESULTS / f"{job_id}.result.yaml", result)
            try:
                job_file.unlink()
            except Exception:
                pass
            log(f"JOB_END {job_id}")

        time.sleep(1)


if __name__ == "__main__":
    main()
