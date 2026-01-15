# ct_runtime/core/audit.py
# =========================================================
# Canonical Audit Writer (Phase 2)
# =========================================================

import sqlite3
from pathlib import Path
from datetime import datetime

# Adjust only if your DB path differs
DB_PATH = Path("/home/zebadiee/ct-runtime/memory/ct_memory.db")


def write_audit_event(
    *,
    actor: str,
    action: str,
    target: str,
    result: str,
    metadata: dict | None = None,
) -> None:
    """
    Canonical audit writer.
    All audit writes MUST pass through this function.
    """
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    meta = metadata or {}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO audit_log (actor, action, target, result, metadata, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            actor,
            action,
            target,
            result,
            repr(meta),
            ts,
        ),
    )

    conn.commit()
    conn.close()
