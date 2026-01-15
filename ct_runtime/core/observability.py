# ct_runtime/core/observability.py
# =========================================================
# Phase 2 — Observability (Read-Only)
# =========================================================

import sqlite3
from pathlib import Path

from ct_runtime.core.config import NODE_ID, SEALED_AUTHORITY_NODE

DB_PATH = Path("/home/zebadiee/ct-runtime/memory/ct_memory.db")


def health() -> dict:
    return {
        "status": "online",
        "node_id": NODE_ID,
    }


def authority() -> dict:
    return {
        "sealed_authority": SEALED_AUTHORITY_NODE,
        "current_node": NODE_ID,
        "is_authority": NODE_ID == SEALED_AUTHORITY_NODE,
    }


def remote_nodes() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT node_id, status, capabilities, first_seen, last_seen
        FROM remote_nodes
    """)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "node_id": r[0],
            "status": r[1],
            "capabilities": r[2],
            "first_seen": r[3],
            "last_seen": r[4],
        }
        for r in rows
    ]
