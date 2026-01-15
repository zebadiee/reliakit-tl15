# ct_runtime/core/federation.py
# =========================================================
# Phase 2 — Federation Skeleton (Read-Only)
# =========================================================

import sqlite3
from datetime import datetime
from pathlib import Path

from ct_runtime.core.audit import write_audit_event

DB_PATH = Path("/home/zebadiee/ct-runtime/memory/ct_memory.db")


def register_node(
    *,
    node_id: str,
    pubkey: str,
    capabilities: list[str],
) -> None:
    """
    Register or refresh a remote node in OBSERVER mode.
    Metadata-only. No execution. No leases.
    """
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO remote_nodes
        (node_id, pubkey, capabilities, status, first_seen, last_seen)
        VALUES (?, ?, ?, 'OBSERVER', ?, ?)
        ON CONFLICT(node_id) DO UPDATE SET
            pubkey=excluded.pubkey,
            capabilities=excluded.capabilities,
            last_seen=excluded.last_seen
        """,
        (
            node_id,
            pubkey,
            ",".join(capabilities),
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()

    write_audit_event(
        actor="SYSTEM",
        action="NODE_REGISTERED",
        target="federation",
        result="OK",
        metadata={
            "node_id": node_id,
            "status": "OBSERVER",
        },
    )
