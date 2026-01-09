#!/usr/bin/env python3
"""
CT Violations Engine
- Scans immutable events
- Flags violations
- Never mutates events
"""

import sqlite3
import time
from datetime import datetime

DB_PATH = "/home/zebadiee/invictus/data/ct_memory.db"
POLL_INTERVAL = 5  # seconds


def db():
    return sqlite3.connect(DB_PATH)


def row_to_event(row):
    return {
        "id": row[0],
        "ts": row[1],
        "agent_id": row[2],
        "type": row[3],
        "payload": row[4],
        "hash": row[5],
        "prev_hash": row[6],
    }


def record_violation(event_id, code, severity, reason, detail):
    d = db()
    c = d.cursor()
    c.execute(
        """
        INSERT INTO violations (
            event_id,
            level,
            reason,
            flagged_at,
            ts,
            code,
            severity,
            detail
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            severity,
            reason,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            code,
            severity,
            detail,
        ),
    )
    d.commit()
    d.close()


def check_event(event):
    event_id = event["id"]
    agent_id = event["agent_id"]
    payload = event["payload"]

    if not agent_id:
        record_violation(
            event_id,
            "ANON_EVENT",
            "warn",
            "Anonymous event detected",
            payload,
        )

    if "escalate" in payload.lower():
        record_violation(
            event_id,
            "ESCALATION_KEYWORD",
            "medium",
            "Escalation keyword used",
            payload,
        )


def main():
    print("[CT-VIOLATIONS] online")
    last_seen_id = 0

    while True:
        d = db()
        c = d.cursor()
        c.execute(
            """
            SELECT id, ts, agent_id, type, payload, hash, prev_hash
            FROM events
            WHERE id > ?
            ORDER BY id ASC
            """,
            (last_seen_id,),
        )

        rows = c.fetchall()
        d.close()

        for row in rows:
            event = row_to_event(row)
            check_event(event)
            last_seen_id = event["id"]

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
