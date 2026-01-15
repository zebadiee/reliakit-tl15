#!/usr/bin/env python3
"""
ct_lease_guard.py

FAIL-CLOSED execution guard for CT Tier-13 leases.
- Registers agent
- Requests lease
- Executes payload only if lease is ISSUED
- Never mutates DB directly
"""

import os
import sys
import json
import time
import subprocess
import argparse
from typing import Dict, Any
from urllib import request, error


# =========================
# CONFIG (EXPLICIT)
# =========================

CT_CORE_URL = os.environ.get("CT_CORE_URL", "http://127.0.0.1:7777")
AGENT_ID = os.environ.get("CT_AGENT_ID")
AGENT_ROLE = os.environ.get("CT_AGENT_ROLE", "executor")
TIMEOUT = int(os.environ.get("CT_HTTP_TIMEOUT", "5"))


# =========================
# HTTP HELPERS
# =========================

def http_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{CT_CORE_URL}{path}"
    data = json.dumps(payload).encode()

    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {path}: {e.read().decode()}")
    except error.URLError as e:
        raise RuntimeError(f"CT_CORE unreachable: {e}")


def http_get(path: str) -> Dict[str, Any]:
    url = f"{CT_CORE_URL}{path}"
    try:
        with request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        raise RuntimeError(f"CT_CORE unreachable: {e}")


# =========================
# CORE GUARD LOGIC
# =========================

def register_agent(agent_id: str, role: str) -> None:
    http_post(
        "/agent/hello",
        {
            "agent_id": agent_id,
            "role": role,
        },
    )


def request_lease(agent_id: str, task_id: str, scope: str, expires_in: int, mode: str) -> Dict[str, Any]:
    lease = http_post(
        "/lease/request",
        {
            "agent_id": agent_id,
            "task_id": task_id,
            "scope": scope,
            "expires_in": expires_in,
            "mode": mode,
        },
    )

    if lease.get("state") != "ISSUED":
        raise RuntimeError(f"Lease denied: {lease}")

    return lease


def complete_lease(agent_id: str, lease_id: str, result: str) -> None:
    """
    Report lease completion to authority.
    result must be "SUCCESS" or "FAILURE"
    """
    try:
        http_post(
            "/lease/complete",
            {
                "agent_id": agent_id,
                "lease_id": lease_id,
                "result": result,
            },
        )
    except Exception as e:
        # Log but don't fail - completion is best-effort accounting
        print(f"Warning: lease completion failed: {e}", file=sys.stderr)


def exec_payload(cmd: list[str]) -> int:
    proc = subprocess.run(cmd)
    return proc.returncode


# =========================
# CLI
# =========================

def main():
    parser = argparse.ArgumentParser(description="CT Lease Execution Guard")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--expires-in", type=int, default=600)
    parser.add_argument("--mode", default="exclusive")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute")

    args = parser.parse_args()

    if not args.cmd:
        print("No command supplied", file=sys.stderr)
        sys.exit(2)

    # Strip leading -- separator if present
    if args.cmd[0] == "--":
        args.cmd = args.cmd[1:]

    if not args.cmd:
        print("No command supplied after --", file=sys.stderr)
        sys.exit(2)

    if not AGENT_ID:
        print("CT_AGENT_ID is required", file=sys.stderr)
        sys.exit(2)

    # 1. Health check (fail closed)
    http_get("/health")

    # 2. Register agent
    register_agent(AGENT_ID, AGENT_ROLE)

    # 3. Request lease
    lease = request_lease(
        agent_id=AGENT_ID,
        task_id=args.task_id,
        scope=args.scope,
        expires_in=args.expires_in,
        mode=args.mode,
    )

    lease_id = lease.get("lease_id")

    # 4. Execute payload
    exit_code = exec_payload(args.cmd)

    # 5. Report completion
    result = "SUCCESS" if exit_code == 0 else "FAILURE"
    complete_lease(AGENT_ID, lease_id, result)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
