#!/usr/bin/env python3
import json, sqlite3, time, requests
from datetime import datetime

DB = "/home/zebadiee/invictus/data/ct_memory.db"
CONFIG = "/home/zebadiee/invictus/ct/notifier_config.json"
LAST_ID_FILE = "/home/zebadiee/invictus/ct/.notifier_last_id"

def load_last_id():
    try:
        return int(open(LAST_ID_FILE).read())
    except:
        return 0

def save_last_id(i):
    open(LAST_ID_FILE, "w").write(str(i))

def notify_pushover(cfg, title, msg, priority=0):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": cfg["api_token"],
            "user": cfg["user_key"],
            "title": title,
            "message": msg,
            "priority": priority
        },
        timeout=5
    )

print("[CT-NOTIFIER] online")

last_id = load_last_id()

while True:
    db = sqlite3.connect(DB)
    c = db.cursor()

    c.execute(
        "SELECT id, payload FROM events WHERE id > ? AND type='ct.notify' ORDER BY id",
        (last_id,)
    )

    rows = c.fetchall()
    for eid, payload in rows:
        data = json.loads(payload)
        severity = data.get("severity", "info")
        requires = data.get("requires_action", False)

        with open(CONFIG) as f:
            cfg = json.load(f)

        if cfg["pushover"]["enabled"]:
            min_sev = cfg["pushover"]["min_severity"]
            levels = ["info", "warning", "critical"]

            if levels.index(severity) >= levels.index(min_sev):
                notify_pushover(
                    cfg["pushover"],
                    f"CT: {severity.upper()}",
                    data.get("message", ""),
                    priority=1 if requires else 0
                )

        last_id = eid
        save_last_id(last_id)

    db.close()
    time.sleep(5)
