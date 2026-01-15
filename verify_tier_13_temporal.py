import requests
import sqlite3
import time
from datetime import datetime, timezone, timedelta

CP = "http://127.0.0.1:7777"
DB = "/home/zebadiee/invictus/data/ct_memory.db"

def get_active_lease():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
        SELECT lease_id
        FROM leases
        WHERE state='ACTIVE'
        ORDER BY issued_at DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    con.close()
    if not row:
        raise SystemExit("No active lease found")
    return row[0]

def try_event(lease_id):
    r = requests.post(
        f"{CP}/event",
        json={
            "agent_id": "gov-executor",
            "lease_id": lease_id,
            "type": "TEST",
            "payload": "temporal-check"
        }
    )
    return r.status_code, r.text

lease_id = get_active_lease()
print(f"[+] Using lease {lease_id}")

# 1) Fence lease into the past
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("""
    UPDATE leases
    SET not_after = ?
    WHERE lease_id = ?
""", ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), lease_id))
con.commit()
con.close()

code, body = try_event(lease_id)
print("[TEST] After not_after:", code, body)
assert code == 403

# 2) Restore valid window
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("""
    UPDATE leases
    SET not_before = ?, not_after = ?
    WHERE lease_id = ?
""", (
    datetime.now(timezone.utc).isoformat(),
    (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    lease_id
))
con.commit()
con.close()

time.sleep(1)
code, body = try_event(lease_id)
print("[TEST] Inside window:", code, body)
assert code == 200

print("\n✔ Tier 13 Temporal Fencing verified")
