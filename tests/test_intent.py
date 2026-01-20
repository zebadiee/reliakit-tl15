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


def test_intent_creates_jobs_and_completes():
    d = sqlite3.connect(DB)
    c = d.cursor()

    # create a lease in ISSUED state
    lease_id = str(uuid.uuid4())
    issued = utcnow_iso()
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    c.execute("INSERT OR REPLACE INTO leases (lease_id, task_id, agent_id, scope, issued_at, expires_at, state, prev_hash, hash, mode, max_consumers) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (lease_id, 'task-x', 'worker-01', 'scope-x', issued, expires, 'ISSUED', '', 'h', 'exclusive', 1))
    d.commit()

    # create a job (manual) referencing the lease
    job_id = str(uuid.uuid4())
    c.execute(
        "INSERT INTO exo_jobs (job_id, agent_id, lease_id, task_id, status, issued_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_id, 'worker-01', lease_id, 'task-x', 'ISSUED', utcnow_iso(), (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
    )
    d.commit()

    # create intent and attach the job
    body = {"description": "Process X", "job_ids": [job_id]}
    res = ct_server.create_intent(body, request=type('rq', (), {'headers':{}})())
    assert 'intent_id' in res and 'attached_jobs' in res
    intent_id = res['intent_id']
    attached = res['attached_jobs']
    assert job_id in attached

    # simulate job completion
    c.execute("UPDATE exo_jobs SET status='COMPLETED', completed_at=? WHERE job_id=?", (utcnow_iso(), job_id))
    d.commit()

    # run intent observer pass and verify intent completed
    changed = ct_server.intent_observer_once()
    assert intent_id in changed

    c.execute("SELECT state, completed_at, narrative FROM intents WHERE intent_id=?", (intent_id,))
    irow = c.fetchone()
    assert irow is not None
    assert irow[0] == 'COMPLETED'
    assert irow[1] is not None
    assert 'COMPLETED' in irow[2] or 'State changed to COMPLETED' in irow[2]

    # verify INTENT_COMPLETED event exists
    c.execute("SELECT type, payload FROM events WHERE type='INTENT_COMPLETED' ORDER BY id DESC LIMIT 1")
    ev = c.fetchone()
    assert ev is not None
    assert 'intent_id' in ev[1]


def test_attach_endpoint():
    d = sqlite3.connect(DB)
    c = d.cursor()

    # create lease and a job
    lease_id = str(uuid.uuid4())
    c.execute("INSERT OR REPLACE INTO leases (lease_id, task_id, agent_id, scope, issued_at, expires_at, state, prev_hash, hash, mode, max_consumers) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (lease_id, 't', 'worker-01', 's', utcnow_iso(), (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), 'ISSUED', '', 'h', 'exclusive', 1))
    job_id = str(uuid.uuid4())
    c.execute("INSERT INTO exo_jobs (job_id, agent_id, lease_id, task_id, status, issued_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (job_id, 'worker-01', lease_id, 't', 'ISSUED', utcnow_iso(), (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()))
    d.commit()

    # create empty intent
    res = ct_server.create_intent({'description': 'attach test'}, request=type('rq', (), {'headers': {}})())
    intent_id = res['intent_id']

    # attach job
    att = ct_server.attach_jobs_to_intent(intent_id, {'job_ids': [job_id]}, request=type('rq', (), {'headers': {}})())
    assert job_id in att['attached_jobs']

    # verify join table and exo_jobs intent_id set
    c.execute("SELECT job_id FROM intent_jobs WHERE intent_id=?", (intent_id,))
    rows = [r[0] for r in c.fetchall()]
    assert job_id in rows
    c.execute("SELECT intent_id FROM exo_jobs WHERE job_id=?", (job_id,))
    r = c.fetchone(); assert r[0] == intent_id

    d.close()
    d.close()
