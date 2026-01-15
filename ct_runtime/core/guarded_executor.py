# ct_runtime/core/guarded_executor.py
# =========================================================
# Phase 2 — Guarded Executor (Fail-Closed)
# =========================================================

from typing import Callable, Any, Dict

from ct_runtime.core.config import NODE_ID, SEALED_AUTHORITY_NODE
from ct_runtime.core.audit import write_audit_event


class ExecutionDenied(Exception):
    pass


def execute_guarded(
    *,
    actor: str,
    action: str,
    scope: str,
    executor: Callable[..., Any],
    payload: Dict[str, Any] | None = None,
) -> Any:
    """
    Single execution choke-point.
    Deny by default.
    Every decision is audited.
    """
    payload = payload or {}

    # Authority enforcement (defensive)
    if NODE_ID != SEALED_AUTHORITY_NODE:
        write_audit_event(
            actor=actor,
            action=action,
            target="execute_guarded",
            result="DENIED",
            metadata={
                "reason": "AUTHORITY_MISMATCH",
                "node_id": NODE_ID,
                "scope": scope,
            },
        )
        raise ExecutionDenied("Authority mismatch")

    try:
        result = executor(**payload)

        write_audit_event(
            actor=actor,
            action=action,
            target="execute_guarded",
            result="OK",
            metadata={
                "node_id": NODE_ID,
                "scope": scope,
            },
        )
        return result

    except Exception as e:
        write_audit_event(
            actor=actor,
            action=action,
            target="execute_guarded",
            result="FAILED",
            metadata={
                "node_id": NODE_ID,
                "scope": scope,
                "error": str(e),
            },
        )
        raise
