MACHINE CONTRACT v1

Status: DRAFT → LOCKABLE
Role: System Interpreter / State Narrator
Deployment Mode: Hermes sidecar (read-only)

1. Identity & Authority

Process name: ct-machine
Host: HERMES only
Role: observer
Mode: LOCKED

Hard assertions (startup)
    • CT_NODE_ID == HERMES
    • CT_MODE == LOCKED
    • CT_ROLE != admin
    • No bind/listen sockets permitted
    • No outbound network calls permitted

If any assertion fails → exit immediately.

2. Purpose (What MACHINE Is)

MACHINE is not an agent.
MACHINE is not a controller.
MACHINE is not an authority.

MACHINE exists to:
    • Observe current system state
    • Correlate events across machines
    • Express what the system is doing and why
    • Surface risk, drift, or readiness signals

3. Inputs (Read-Only)

From Hermes (localhost only)
    • GET /health
    • GET /agents
    • GET /tasks/summary
    • GET /state/lock
    • GET /state/version

No POST. No mutation. No task enqueue.

From Atlas (filesystem, read-only)
    • /srv/ct/atlas/events/*.jsonl
    • /srv/ct/atlas/decisions/*.jsonl
    • /srv/ct/atlas/audit_flags/*.jsonl

Ledger integrity must be verified before use.

From Environment
    • CT_VERSION
    • CT_CONTRACT_TAG
    • CT_SNAPSHOT_ID (if present)

4. Outputs (Strict)

MACHINE may output only:
    1. STDOUT
       • Human-readable system narration
       • Deterministic, timestamped
    2. Optional state file (tmpfs only)
       • /run/ct/machine.state
       • JSON
       • Overwritten, never appended

No logs to disk.
No DB writes.
No network output.

5. Behavioural Invariants

MACHINE MUST:
    • Never cache authority state across restarts
    • Never assume intent
    • Never invent future actions
    • Always distinguish:
        • Observed fact
        • Derived inference
        • Unknown / ambiguous

6. Failure Semantics

Atlas ledger fails verification → Emit CRITICAL, exit
Hermes unreachable → Emit DEGRADED, retry
Env invariant violated → Exit immediately
Unexpected exception → Emit ERROR, exit

7. Forbidden Capabilities (Permanent)

MACHINE may never:
    • Call /task/* endpoints
    • Register as an agent
    • Write to Atlas
    • Spawn subprocesses
    • Accept external input
    • Be imported by other modules

8. Relationship to Other Components

    • Hermes: source of truth
    • Atlas: memory & evidence
    • Hades: execution surface

9. Lock Conditions

This contract becomes LOCKED when:
    • Tagged as ct-machine-v1
    • systemd unit enforces sandboxing (ProtectSystem=strict, ProtectHome=true, PrivateNetwork=true, NoNewPrivileges=true)

10. What Happens Next

Next steps, in order:
    1. Implement machine.py (pure read-only)
    2. Create ct-machine.service (sidecar, sandboxed)
    3. Run in silent observe mode (no UI, no prompts)
