import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ct_runtime import ct_server

DB = ct_server.DB_PATH


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def test_failover_reassigns_job():
    d = sqlite3.connect(DB)
    c = d.cursor()

    # ensure agents exist: worker-01 (stale), worker-02 (online)
    stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    live_ts = utcnow_iso()

    c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at, last_seen, status) VALUES (?, ?, 0, ?, ?, ?)",
              ('worker-01', 'executor', utcnow_iso(), stale_ts, 'STALE'))
    c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at, last_seen, status) VALUES (?, ?, 0, ?, ?, ?)",
              ('worker-02', 'executor', utcnow_iso(), live_ts, 'ONLINE'))

    # create a RUNNING job on worker-01 with started_at old
    job_id = str(uuid.uuid4())
    started = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    c.execute(
        "INSERT INTO exo_jobs (job_id, agent_id, lease_id, task_id, status, issued_at, expires_at, started_at, attempts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (job_id, 'worker-01', 'lease-x', 'task-x', 'RUNNING', utcnow_iso(), (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), started, 0)
    )
    d.commit()
    d.close()

    # perform a quick failover pass
    reassigned = ct_server.failover_once(timeout_seconds=1)

    assert job_id in reassigned

    # verify job reassigned to worker-02 and marked ISSUED
    d = sqlite3.connect(DB)
    c = d.cursor()
    c.execute("SELECT agent_id, status, attempts FROM exo_jobs WHERE job_id=?", (job_id,))
    row = c.fetchone()
    d.close()

    assert row is not None
    assert row[0] == 'worker-02'
    assert row[1] == 'ISSUED'
    assert row[2] >= 1


def test_failover_logs_event():
    d = sqlite3.connect(DB)
    c = d.cursor()
    # find most recent TASK_REASSIGN event
    c.execute("SELECT type, payload FROM events WHERE type='TASK_REASSIGN' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    d.close()
    assert row is not None
    assert row[0] == 'TASK_REASSIGN'
    assert 'job_id' in row[1] or 'job_id' in row[1]
