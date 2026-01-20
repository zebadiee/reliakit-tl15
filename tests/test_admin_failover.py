import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from importlib import util
spec = util.spec_from_file_location("ct_server", "/home/zebadiee/ct-runtime/ct_server.py")
ct_server = util.module_from_spec(spec)
spec.loader.exec_module(ct_server)
DB = ct_server.DB_PATH


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def test_admin_failover_endpoint():
    d = sqlite3.connect(DB)
    c = d.cursor()

    # setup admin agent
    now = utcnow_iso()
    c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at, last_seen, status) VALUES (?, ?, 0, ?, ?, ?)",
              ('admin-1', 'admin', now, now, 'ONLINE'))

    # setup executor agents
    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    live_ts = utcnow_iso()
    c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at, last_seen, status) VALUES (?, ?, 0, ?, ?, ?)",
              ('worker-01', 'executor', now, stale_ts, 'STALE'))
    c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at, last_seen, status) VALUES (?, ?, 0, ?, ?, ?)",
              ('worker-02', 'executor', now, live_ts, 'ONLINE'))

    # create a RUNNING job assigned to worker-01 with old started_at
    job_id = str(uuid.uuid4())
    started = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    c.execute(
        "INSERT INTO exo_jobs (job_id, agent_id, lease_id, task_id, status, issued_at, expires_at, started_at, attempts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (job_id, 'worker-01', 'lease-x', 'task-x', 'RUNNING', utcnow_iso(), (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), started, 0)
    )
    d.commit()

    # call admin endpoint (simulate request object)
    res = ct_server.admin_failover_once(request=type('rq', (), {'headers': {'X-Agent-ID': 'admin-1'}})())
    assert 'reassigned' in res
    assert job_id in res['reassigned']

    # verify TASK_REASSIGN event exists
    c.execute("SELECT type, payload FROM events WHERE type='TASK_REASSIGN' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    assert row is not None
    assert 'job_id' in row[1]

    d.close()
