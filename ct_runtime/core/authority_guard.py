# ct_runtime/core/authority_guard.py
# =========================================================
# Phase 2 — Authority Guard (Sealed Governance)
# =========================================================

import sys
from ct_runtime.core.audit import write_audit_event


class AuthorityViolation(Exception):
    pass


def assert_authority_or_exit(node_id: str, sealed_authority: str) -> None:
    """
    Hard authority invariant.
    MUST run at process start for any executable entry point.

    Fail-closed: process exits if node != sealed authority.
    Always emits a boot audit event: PASSED or FAILED.
    """
    try:
        if node_id != sealed_authority:
            raise AuthorityViolation(
                f"node_id '{node_id}' != sealed_authority '{sealed_authority}'"
            )

        write_audit_event(
            actor="SYSTEM",
            action="AUTHORITY_ASSERTION_PASSED",
            target="authority_guard",
            result="OK",
            metadata={
                "node_id": node_id,
                "sealed_authority": sealed_authority,
            },
        )

    except Exception as e:
        write_audit_event(
            actor="SYSTEM",
            action="AUTHORITY_ASSERTION_FAILED",
            target="authority_guard",
            result="DENIED",
            metadata={
                "node_id": node_id,
                "sealed_authority": sealed_authority,
                "error": str(e),
            },
        )
        sys.stderr.write(f"\n[FATAL] AUTHORITY VIOLATION: {e}\n")
        sys.exit(100)
