#!/usr/bin/env python3

import sqlite3
import time
from datetime import datetime
import json
import sys

DB_PATH = "/home/zebadiee/invictus/data/ct_memory.db"
POLL_INTERVAL = 5  # seconds

ALLOWED_TYPES = {"cli", "status", "agent", "system"}

# ------------------------
# Database helpers
# ------------------------

def db():
    return sqlite3.connect(DB_PATH)

def now():
    return datetime.utcnow().isoformat()

# ------------------------
# Benchmarks
# ------------------------

def achieved(key: str) -> bool:
    d = db()
    c = d.cursor()
    c.execute("SELECT 1 FROM benchmarks WHERE key=?", (key,))
    r = c.fetchone()
    d.close()
    return r is not None

def mark(key: str):
    d = db()
    c = d.cursor()
    c.execute(
        "INSERT OR IGNORE INTO benchmarks (key, achieved_at) VALUES (?, ?)",
        (key, now())
    )
    d.commit()
    d.close()

# ------------------------
# Notifications
# ------------------------

def notify(level: str, message: str):
    d = db()
    c = d.cursor()
    c.execute(
        "INSERT INTO notifications (level, message, created_at) VALUES (?, ?, ?)",
        (level, message, now())
    )
    d.commit()
    d.close()

# ------------------------
# Violations
# ------------------------

def flag(event_id: int, level: str, reason: str):
    d = db()
    c = d.cursor()
    c.execute(
        "INSERT INTO violations (event_id, level, reason, flagged_at) VALUES (?, ?, ?, ?)",
        (event_id, level, reason, now())
    )
    d.commit()
    d.close()

# ------------------------
# Observer loop
# ------------------------

def observe():
    print("[CT-OBSERVER] online", flush=True)

    last_id = 0
    last_hash = ""

    while True:
        try:
            d = db()
            c = d.cursor()
            c.execute(
                """
                SELECT id, ts, agent_id, type, payload, hash, prev_hash
                FROM events
                WHERE id > ?
                ORDER BY id ASC
                """,
                (last_id,)
            )
            rows = c.fetchall()
            d.close()

            for row in rows:
                event = {
                    "id": row[0],
                    "ts": row[1],
                    "agent_id": row[2],
                    "type": row[3],
                    "payload": row[4],
                    "hash": row[5],
                    "prev_hash": row[6],
                }

                # ---- Hash chain integrity
                if last_hash and event["prev_hash"] != last_hash:
                    flag(event["id"], "block", "hash chain broken")

                last_hash = event["hash"] or last_hash
                last_id = event["id"]

                # ---- Unknown event types
                if event["type"] not in ALLOWED_TYPES:
                    flag(event["id"], "warn", f"unknown event type: {event['type']}")

                # ---- Benchmark: first agent event
                if not achieved("first_agent_event"):
                    if event["agent_id"]:
                        mark("first_agent_event")
                        notify("info", "First agent event recorded")

                # ---- Example escalation rule
                if event["type"] == "status" and "escalation" in event["payload"].lower():
                    notify("info", f"Escalation noted from {event['agent_id']}")

                # ---- Emit observation (stdout only)
                print(json.dumps({
                    "observed_at": now(),
                    "event": event
                }), flush=True)

        except Exception as e:
            notify("escalate", f"observer error: {e}")
            print(f"[CT-OBSERVER] ERROR: {e}", file=sys.stderr, flush=True)

        time.sleep(POLL_INTERVAL)

# ------------------------
# Entry point
# ------------------------

if __name__ == "__main__":
    observe()
