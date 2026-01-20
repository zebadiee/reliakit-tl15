# =========================================================
# Phase 2 — Sealed Authority Guard (MUST RUN FIRST)
# =========================================================
from ct_runtime.core.config import NODE_ID, SEALED_AUTHORITY_NODE
from ct_runtime.core.authority_guard import assert_authority_or_exit

assert_authority_or_exit(NODE_ID, SEALED_AUTHORITY_NODE)

#!/usr/bin/env python3
import os
import sqlite3
import hashlib
import uuid
import json
import asyncio
import time
import socket
NODE_ID = socket.gethostname()
import base64
CT_DB_SEALED = os.getenv("CT_DB_SEALED") == "1"
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse

# =========================================================
# Core identity
# =========================================================

NODE_ID = os.environ.get("CT_NODE_ID", "invictus")
NODE_ROLE = os.environ.get("CT_NODE_ROLE", "authoritative")

BASE = os.path.expanduser("~/invictus")
DATA_DIR = os.environ.get("CT_DATA", f"{BASE}/data")
DB_PATH = os.path.join(DATA_DIR, "ct_memory.db")

# Network / auth hardening toggles (safe defaults)
REQUIRE_TAILSCALE = os.environ.get("CT_REQUIRE_TAILSCALE", "0") == "1"
REQUIRE_SIGNATURES = os.environ.get("CT_REQUIRE_SIGS", "0") == "1"


# =========================================================
# Governance Memory (Obsidian)
# =========================================================
OBSIDIAN_PATH = os.environ.get("CT_OBSIDIAN_PATH", os.path.expanduser("~/Obsidian/CT-Governance"))
os.makedirs(OBSIDIAN_PATH, exist_ok=True)

def log_governance_event(title: str, details: dict):
    ts = datetime.now(timezone.utc).isoformat()
    log_path = os.path.join(OBSIDIAN_PATH, "03-Governance-Log.md")
    if not os.path.exists(log_path):
        with open(log_path, "w") as f: f.write("# Governance Activity Log\n")
    with open(log_path, "a") as f:
        f.write(f"\n## {ts} — {title}\n")
        for k, v in details.items():
            f.write(f"- **{k}**: {v}\n")

def write_policy_registry():
    path = os.path.join(OBSIDIAN_PATH, "04-Policy-Registry.md")
    d = db(); c = d.cursor()
    c.execute("SELECT policy_id, version, rules, status FROM policies")
    rows = c.fetchall(); d.close()
    with open(path, "w") as f:
        f.write("# Active Governance Policies\n\n")
        for pid, ver, rules_json, status in rows:
            f.write(f"## {pid} (v{ver})\n")
            f.write(f"- Status: {status}\n")
            f.write(f"- Rules:\n```json\n{json.dumps(json.loads(rules_json), indent=2)}\n```\n\n")
app = FastAPI(title="CT Invictus Control Plane")

# Capability mapping
SCOPE_CAPABILITIES = {
    "noop": [],
    "run": ["run_task"],
    "models": ["read_models"],
    "full": ["run_task", "read_models", "emit_events", "manage_resources"],
}

# Governance constants for nodes
ALLOWED_NODE_CAPABILITIES = {"infer", "train", "store", "route", "model_host"}

# =========================================================
# Optional crypto (Ed25519 verification)
# =========================================================

_CRYPTO_OK = False
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db():
    return sqlite3.connect(DB_PATH)


def hash_chain(prev: str, ts: str, agent: str, etype: str, payload: str) -> str:
    h = hashlib.sha256()
    h.update((prev or "").encode())
    h.update(ts.encode())
    h.update(agent.encode())
    h.update(etype.encode())
    h.update(payload.encode())
    return h.hexdigest()


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)

    if CT_DB_SEALED:
        if not os.path.exists(DB_PATH):
            raise RuntimeError("SEALED MODE: database missing")
        return

    d = sqlite3.connect(DB_PATH)
    c = d.cursor()
    # existing schema + seed logic stays below
    c.execute("""
    CREATE TABLE IF NOT EXISTS node_identity (
        node_id TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        locked INTEGER NOT NULL,
        locked_at TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        agent_id TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        type TEXT NOT NULL,
        payload TEXT NOT NULL,
        prev_hash TEXT,
        hash TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS leases (
        lease_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        scope TEXT NOT NULL,
        issued_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        state TEXT NOT NULL,
        prev_hash TEXT,
        hash TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'exclusive',
        max_consumers INTEGER NOT NULL DEFAULT 1
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS lease_consumers (
        lease_id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL,
        bound_at TEXT NOT NULL,
        FOREIGN KEY (lease_id) REFERENCES leases(lease_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS agent_keys (
        agent_id TEXT PRIMARY KEY,
        pubkey TEXT NOT NULL,
        added_at TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS roles_permissions (
        role TEXT NOT NULL,
        capability TEXT NOT NULL,
        PRIMARY KEY (role, capability)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS lease_capabilities (
        lease_id TEXT NOT NULL,
        capability TEXT NOT NULL,
        PRIMARY KEY (lease_id, capability)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS lease_resources (
        lease_id TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        permission TEXT NOT NULL,
        PRIMARY KEY (lease_id, resource_type, resource_id, permission)
    )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS remote_nodes (
            node_id TEXT PRIMARY KEY,
            pubkey TEXT NOT NULL,
            capabilities TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            status TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS federation_nonces (
            nonce TEXT PRIMARY KEY,
            seen_at INTEGER NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS heartbeat_nonces (
            nonce TEXT PRIMARY KEY,
            seen_at INTEGER NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            policy_id TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            rules JSON NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Orchestrator: intents table (CT-ORCHESTRATOR v1)
    c.execute("""
    CREATE TABLE IF NOT EXISTS intents (
        intent_id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        constraints JSON NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        -- CT-ORCHESTRATOR additions
        state TEXT,
        narrative TEXT
    )
    """)

    # join table linking intents to jobs (loose coupling)
    c.execute("""
    CREATE TABLE IF NOT EXISTS intent_jobs (
        intent_id TEXT NOT NULL,
        job_id TEXT NOT NULL,
        PRIMARY KEY (intent_id, job_id)
    )
    """)
    c.executemany("INSERT OR IGNORE INTO roles_permissions (role, capability) VALUES (?, ?)", seed)

    c.execute("SELECT COUNT(*) FROM node_identity")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO node_identity VALUES (?, ?, ?, ?)", (NODE_ID, NODE_ROLE, 1, utcnow_iso()))

    d.commit()
    d.close()


def ensure_exo_jobs_columns():
    d = db(); c = d.cursor()
    try:
        c.execute("PRAGMA table_info(exo_jobs)")
        cols = [r[1] for r in c.fetchall()]
        if 'lease_id' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN lease_id TEXT")
        if 'task_id' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN task_id TEXT")
        if 'completed_at' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN completed_at TEXT")
        if 'receipt' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN receipt TEXT")
        # Fields required for failover
        if 'started_at' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN started_at TEXT")
        if 'attempts' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN attempts INTEGER DEFAULT 0")
        # Field required for intents
        if 'intent_id' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN intent_id TEXT")
        d.commit()
    except Exception:
        pass
    finally:
        d.close()

if not os.environ.get("CT_DB_SEALED"):
    init_db()
    ensure_exo_jobs_columns()
    # ensure agents table has liveness columns for failover
    def ensure_agents_columns():
        d = db(); c = d.cursor()
        try:
            c.execute("PRAGMA table_info(agents)")
            cols = [r[1] for r in c.fetchall()]
            if 'last_seen' not in cols:
                c.execute("ALTER TABLE agents ADD COLUMN last_seen TEXT")
            if 'status' not in cols:
                c.execute("ALTER TABLE agents ADD COLUMN status TEXT DEFAULT 'ONLINE'")
            d.commit()
        except Exception:
            pass
        finally:
            d.close()
    ensure_agents_columns()
    # ensure failover/orchestrator schema exists for existing DBs
    try:
        ensure_failover_schema()
    except Exception:
        pass

# =========================================================
# Middleware
# =========================================================

def _is_tailscale_ip(ip: str) -> bool:
    if ip in ("127.0.0.1", "::1"): return True
    return ip.startswith("100.")

@app.middleware("http")
async def tailscale_only(request: Request, call_next):
    if REQUIRE_TAILSCALE:
        client_ip = request.client.host if request.client else ""
        if not _is_tailscale_ip(client_ip):
            return JSONResponse({"detail": "tailscale-only"}, status_code=403)
    return await call_next(request)

# =========================================================
# Models
# =========================================================

class ResourceConstraint(BaseModel):
    type: str
    id: str
    perm: str

class LeaseRequest(BaseModel):
    agent_id: str
    task_id: str
    scope: str
    resources: Optional[List[ResourceConstraint]] = None
    nonce: Optional[str] = None
    signature: Optional[str] = None
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    parent_lease_id: Optional[str] = None
class LeaseComplete(BaseModel):
    agent_id: str
    lease_id: str
    success: bool = True
    receipt: Optional[str] = None

class ModelInvoke(BaseModel):
    agent_id: str
    lease_id: str
    model_id: str
    prompt: str

class NodeRegister(BaseModel):
    node_id: str
    pubkey: str
    capabilities: List[str]

class SignedNodeRegister(BaseModel):
    payload: NodeRegister
    nonce: str
    timestamp: int
    signature: str

class FederationAuthorize(BaseModel):
    node_id: str
    agent_id: str
    lease_id: str
    resource_type: str
    resource_id: str
    permission: str
    nonce: str
    signature: str

class SignedHeartbeat(BaseModel):
    payload: Dict[str, str]  # { "node_id": str }
    nonce: str
    timestamp: int
    signature: str

class NodeRevoke(BaseModel):
    target_node_id: str
    reason: str
    nonce: str
    signature: str

class LeaseRevoke(BaseModel):
    lease_id: str
    reason: str
    nonce: str
    signature: str

class PolicyRules(BaseModel):
    capability_ceiling: Optional[List[str]] = None
    time_window: Optional[Dict[str, str]] = None # {"start": "HH:MM", "end": "HH:MM"}
    restricted_nodes: Optional[List[str]] = None
    agent_node_blocks: Optional[List[str]] = None

class PolicyUpdate(BaseModel):
    policy_id: str
    rules: PolicyRules
    nonce: str
    signature: str

# =========================================================
# Helpers / Guards
# =========================================================

def require_active_lease(lease_id: str, agent_id: Optional[str] = None):
    d = db()
    c = d.cursor()
    c.execute(
        "SELECT agent_id, expires_at, state FROM leases WHERE lease_id=?",
        (lease_id,)
    )
    row = c.fetchone()
    d.close()

    if not row:
        raise HTTPException(status_code=403, detail="Lease not found")

    db_agent, expires_at, state = row

    if agent_id and db_agent != agent_id:
        raise HTTPException(status_code=403, detail="Agent mismatch")

    if state != "ISSUED":
        raise HTTPException(status_code=403, detail=f"Lease not active: {state}")

    if expires_at:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(status_code=403, detail="Lease expired")

def require_capability(lease_id: str, capability: str, agent_id: Optional[str] = None):
    require_active_lease(lease_id, agent_id)
    d = db(); c = d.cursor()
    c.execute("SELECT 1 FROM lease_capabilities WHERE lease_id=? AND capability=?", (lease_id, capability))
    ok = c.fetchone() is not None; d.close()
    if not ok: raise HTTPException(403, f"missing required capability: {capability}")

def require_resource_access(lease_id: str, res_type: str, res_id: str, perm: str, agent_id: Optional[str] = None):
    require_active_lease(lease_id, agent_id)
    d = db(); c = d.cursor()
    c.execute("SELECT 1 FROM lease_resources WHERE lease_id=? AND resource_type=? AND resource_id=? AND permission=?", (lease_id, res_type, res_id, perm))
    ok = c.fetchone() is not None; d.close()
    if not ok: raise HTTPException(403, f"resource access denied: {res_type}:{res_id} [{perm}]")

# Tier 14: Delegation
# =========================================================

MAX_DELEGATION_DEPTH = 2

def require_valid_delegation(parent_lease_id: str, child_nb, child_na):
    d = db(); c = d.cursor()
    c.execute("""
        SELECT not_before, not_after, state, delegation_depth
        FROM leases WHERE lease_id=?
    """, (parent_lease_id,))
    row = c.fetchone(); d.close()

    if not row:
        raise HTTPException(403, "invalid parent lease")

    p_nb, p_na, state, depth = row

    if state != "ACTIVE":
        raise HTTPException(403, "parent lease not active")

    if depth >= MAX_DELEGATION_DEPTH:
        raise HTTPException(403, "delegation depth exceeded")

    nb_dt = datetime.fromisoformat(p_nb)
    na_dt = datetime.fromisoformat(p_na)

    if child_nb < nb_dt:
        raise HTTPException(403, "child lease starts before parent")

    if child_na > na_dt:
        raise HTTPException(403, "child lease exceeds parent window")

def revoke_lease_tree(lease_id: str):
    """Revoke a lease and all its children recursively."""
    d = db(); c = d.cursor()
    c.execute("UPDATE leases SET state='REVOKED' WHERE lease_id=?", (lease_id,))
    c.execute("SELECT lease_id FROM leases WHERE parent_lease_id=?", (lease_id,))
    children = [r[0] for r in c.fetchall()]
    d.commit(); d.close()
    
    log_governance_event("Delegation Cascade Revoked", {
        "root_lease": lease_id,
        "children_revoked": len(children)
    })
    
    for child in children:
        revoke_lease_tree(child)

# =========================================================
# Policy Evaluator
# =========================================================

def evaluate_policy(context: Dict[str, Any]):
    """Evaluates all ACTIVE policies against a context."""
    d = db(); c = d.cursor()
    c.execute("SELECT rules FROM policies WHERE status='ACTIVE'")
    policies = c.fetchall(); d.close()
    
    now = datetime.now(timezone.utc)
    current_time_str = now.strftime("%H:%M")
    
    for (rules_json,) in policies:
        rules = json.loads(rules_json)
        
        # 1. Capability Ceiling
        ceiling = rules.get("capability_ceiling")
        if ceiling and "requested_caps" in context:
            for cap in context["requested_caps"]:
                if cap not in ceiling:
                    raise HTTPException(403, f"Policy violation: capability '{cap}' exceeds ceiling")
        
        # 2. Time Window
        window = rules.get("time_window")
        if window:
            start = window.get("start")
            end = window.get("end")
            if start and end:
                if not (start <= current_time_str <= end):
                    raise HTTPException(403, f"Policy violation: outside allowed window {start}-{end}")
        
        # 3. Restricted Nodes
        restricted = rules.get("restricted_nodes")
        if restricted and "node_id" in context:
            if context["node_id"] in restricted:
                raise HTTPException(403, f"Policy violation: node '{context['node_id']}' is restricted")

        # 4. Agent-Node Pairing Restrictions
        agent_node_blocks = rules.get("agent_node_blocks")
        if agent_node_blocks and "agent_id" in context and "node_id" in context:
            pair = f"{context['agent_id']}:{context['node_id']}"
            if pair in agent_node_blocks:
                raise HTTPException(403, f"Policy violation: agent {context['agent_id']} is blocked from node {context['node_id']}")

# =========================================================
# Endpoints
# =========================================================

@app.get("/health")
def health(): return {"status": "online", "node": NODE_ID}

@app.get("/identity")
def identity():
    d = db(); c = d.cursor()
    c.execute("SELECT node_id, role, locked, locked_at FROM node_identity LIMIT 1")
    row = c.fetchone(); d.close()
    return {"node_id": row[0], "role": row[1], "locked": bool(row[2]), "locked_at": row[3]}
@app.post("/agent/hello")
def agent_hello(body: dict):
    agent_id = body.get("agent_id")
    role = body.get("role", "executor")

    if not agent_id:
        raise HTTPException(400, "agent_id required")

    # HARD RULE: sealed means ZERO writes
    if CT_DB_SEALED:
        return {
            "node": NODE_ID,
            "agent_role": "readonly",
            "sealed": True
        }

    d = db()
    c = d.cursor()
    c.execute(
        "INSERT OR IGNORE INTO agents (agent_id, role, revoked, created_at) VALUES (?, ?, ?, ?)",
        (agent_id, role, 0, utcnow_iso())
    )
    d.commit()
    d.close()

    return {
        "node": NODE_ID,
        "agent_role": role,
        "sealed": False
    }

@app.post("/agent/heartbeat")
def agent_heartbeat(body: dict):
    """Agent heartbeat to mark liveness for failover decisions.

    Body: { agent_id }
    """
    agent_id = body.get("agent_id")
    if not agent_id:
        raise HTTPException(400, "agent_id required")
    d = db(); c = d.cursor()

    # Update existing agent or insert minimal record
    c.execute("UPDATE agents SET last_seen=?, status='ONLINE' WHERE agent_id=?", (utcnow_iso(), agent_id))
    if c.rowcount == 0:
        c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at, last_seen, status) VALUES (?, ?, 0, ?, ?, 'ONLINE')",
                  (agent_id, 'executor', utcnow_iso(), utcnow_iso()))
    d.commit(); d.close()
    return {"status": "OK", "agent_id": agent_id}

@app.post("/admin/register_key")
def register_key(body: dict):
    agent_id = body.get("agent_id"); pubkey = body.get("pubkey")
    if not agent_id or not pubkey: raise HTTPException(400, "agent_id/pubkey required")
    d = db(); c = d.cursor()
    c.execute("INSERT OR REPLACE INTO agent_keys (agent_id, pubkey, added_at) VALUES (?, ?, ?)", (agent_id, pubkey.strip(), utcnow_iso()))
    d.commit(); d.close()
    return {"ok": True}

# =========================================================
# Actions
# =========================================================

def _verify_ed25519(agent_id: str, message: str, signature_b64: str) -> bool:
    if not REQUIRE_SIGNATURES: return True
    if not _CRYPTO_OK: raise HTTPException(503, "crypto missing")
    d = db(); c = d.cursor()
    c.execute("SELECT pubkey FROM agent_keys WHERE agent_id=?", (agent_id,))
    row = c.fetchone(); d.close()
    if not row: raise HTTPException(403, "no key")
    keydata = base64.b64decode(row[0].split()[1].encode())
    def read_u32(b, off): return int.from_bytes(b[off:off+4], "big"), off+4
    def read_str(b, off):
        ln, off = read_u32(b, off)
        return b[off:off+ln], off+ln
    off = 0; t, off = read_str(keydata, off); k, off = read_str(keydata, off)
    pk = Ed25519PublicKey.from_public_bytes(k)
    sig = base64.b64decode(signature_b64.encode())
    try: pk.verify(sig, message.encode()); return True
    except: return False

@app.post("/lease/request")
def lease_request(req: LeaseRequest):
    """
    CONSUME-ONLY LEASE ENDPOINT (Model A)
    Executors may only consume pre-issued leases.
    No lease creation occurs here.
    """
    now = utcnow_iso()

    d = db()
    c = d.cursor()

    c.execute(
        """
        SELECT lease_id, expires_at, state, mode
        FROM leases
        WHERE agent_id = ?
          AND task_id = ?
          AND scope = ?
          AND state = 'ISSUED'
        ORDER BY issued_at DESC
        LIMIT 1
        """,
        (req.agent_id, req.task_id, req.scope)
    )

    row = c.fetchone()
    d.close()

    if not row:
        raise HTTPException(
            status_code=403,
            detail="No pre-issued lease found"
        )

    lease_id, expires_at, state, mode = row

    if expires_at <= now:
        raise HTTPException(
            status_code=403,
            detail="Lease expired"
        )

    return {
        "lease_id": lease_id,
        "agent_id": req.agent_id,
        "scope": req.scope,
        "state": state,
        "expires_at": expires_at,
        "mode": mode,
    }

@app.post("/event")
def log_event(body: dict):
    agent_id = body.get("agent_id")
    etype = body.get("type", "GENERIC")
    payload = body.get("payload", {})

    if not agent_id:
        raise HTTPException(400, "agent_id required")

    ts = utcnow_iso()

    # === SEALED MODE: audit-only, no lease, no capability ===
    if CT_DB_SEALED:
        d = sqlite3.connect(DB_PATH)
        c = d.cursor()
        c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
        prev = c.fetchone()
        prev_hash = prev[0] if prev else ""
        h = hash_chain(prev_hash, ts, agent_id, etype, json.dumps(payload))
        c.execute(
            "INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, agent_id, etype, json.dumps(payload), prev_hash, h)
        )
        d.commit()
        d.close()
        return {"ok": True, "sealed": True, "hash": h}

    # === UNSEALED MODE: require lease + capability ===
    lease_id = body.get("lease_id")
    if not lease_id:
        raise HTTPException(403, "lease_id required")

    require_capability(lease_id, "emit_events", agent_id=agent_id)

    d = db()
    c = d.cursor()
    c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
    prev = c.fetchone()
    prev_hash = prev[0] if prev else ""
    h = hash_chain(prev_hash, ts, agent_id, etype, json.dumps(payload))
    c.execute(
        "INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ts, agent_id, etype, json.dumps(payload), prev_hash, h)
    )
    d.commit()
    d.close()

    return {"ok": True, "sealed": False, "hash": h}

@app.post("/model/call")
def model_call(req: ModelInvoke):
    require_capability(req.lease_id, "run_task", agent_id=req.agent_id)
    require_resource_access(req.lease_id, "model", req.model_id, "invoke", agent_id=req.agent_id)
    return {"status": "success", "model": req.model_id, "response": f"Mock response from {req.model_id}..."}

# =========================================================
# Task execution endpoints (gated)
# =========================================================
class TaskExecute(BaseModel):
    agent_id: Optional[str] = None
    lease_id: str
    task_id: str
    command: Optional[str] = None

# Helper: pick least-busy worker agent
def pick_least_busy_worker(exclude_agent: Optional[str] = None) -> Optional[str]:
    d = db(); c = d.cursor()
    # let SQLite choose randomly among ties using RANDOM(); restrict to 'executor' role
    if exclude_agent:
        c.execute("""
            SELECT a.agent_id
            FROM agents a
            LEFT JOIN (
                SELECT agent_id, COUNT(*) as cnt
                FROM exo_jobs
                WHERE status IN ('ISSUED','RUNNING')
                GROUP BY agent_id
            ) j ON a.agent_id = j.agent_id
            WHERE a.role='executor' AND a.revoked=0 AND a.agent_id != ?
            ORDER BY COALESCE(j.cnt, 0) ASC, RANDOM()
            LIMIT 1
        """, (exclude_agent,))
    else:
        c.execute("""
            SELECT a.agent_id
            FROM agents a
            LEFT JOIN (
                SELECT agent_id, COUNT(*) as cnt
                FROM exo_jobs
                WHERE status IN ('ISSUED','RUNNING')
                GROUP BY agent_id
            ) j ON a.agent_id = j.agent_id
            WHERE a.role='executor' AND a.revoked=0
            ORDER BY COALESCE(j.cnt, 0) ASC, RANDOM()
            LIMIT 1
        """)
    row = c.fetchone(); d.close()
    return row[0] if row else None

class TaskStatus(BaseModel):
    job_id: str
    status: str
    agent_id: str
    task_id: Optional[str]
    issued_at: str
    expires_at: str

class IntentRequest(BaseModel):
    description: str
    job_ids: Optional[List[str]] = None


@app.post("/intent")
def create_intent(body: dict, request: Request):
    """Create an intent as a semantic wrapper. No scheduling occurs here.

    Body: { description, job_ids: [<job_id>, ...] }

    Access: disallow calls coming from agents with role 'executor' (workers).
    """
    description = body.get("description")
    job_ids = body.get("job_ids") or []

    if not description:
        raise HTTPException(400, "description required")

    # Guard: if caller provided X-Agent-ID and that agent is a worker (executor), deny
    caller_agent = request.headers.get("X-Agent-ID")
    if caller_agent:
        d = db(); c = d.cursor()
        c.execute("SELECT role FROM agents WHERE agent_id=?", (caller_agent,))
        row = c.fetchone()
        d.close()
        if row and row[0] == 'executor':
            raise HTTPException(403, "workers may not create intents")

    intent_id = str(uuid.uuid4())
    created_at = utcnow_iso()
    d = db(); c = d.cursor()
    # set initial state to PENDING and empty narrative
    c.execute("INSERT INTO intents (intent_id, description, constraints, status, created_at, state, narrative) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (intent_id, description, json.dumps({}), "CREATED", created_at, 'PENDING', ''))
    d.commit()

    # immutable event: INTENT_CREATED
    try:
        ts = utcnow_iso()
        c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
        prev = c.fetchone(); prev_hash = prev[0] if prev else ""
        payload = json.dumps({"intent_id": intent_id, "description": description})
        h = hash_chain(prev_hash, ts, "SYSTEM", "INTENT_CREATED", payload)
        c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, "SYSTEM", "INTENT_CREATED", payload, prev_hash, h))
        d.commit()
    except Exception:
        pass

    # Attach provided job_ids (if any) but DO NOT change job state
    attached = []
    for jid in job_ids:
        # check job exists
        c.execute("SELECT 1 FROM exo_jobs WHERE job_id=?", (jid,))
        if c.fetchone():
            c.execute("INSERT OR IGNORE INTO intent_jobs (intent_id, job_id) VALUES (?, ?)", (intent_id, jid))
            # also set exo_jobs.intent_id for convenience
            c.execute("UPDATE exo_jobs SET intent_id=? WHERE job_id=?", (intent_id, jid))
            attached.append(jid)
    d.commit()

    # Append initial narrative
    append_intent_narrative(intent_id, f"Intent created with {len(attached)} attached jobs")

    d.close()
    return {"intent_id": intent_id, "attached_jobs": attached}


@app.post("/intent/{intent_id}/attach")
def attach_jobs_to_intent(intent_id: str, body: dict, request: Request):
    """Attach existing job_ids to an intent. Does not modify job state."""
    job_ids = body.get("job_ids") or []
    if not job_ids:
        raise HTTPException(400, "job_ids required")

    # Guard: disallow worker callers
    caller_agent = request.headers.get("X-Agent-ID")
    if caller_agent:
        d = db(); c = d.cursor()
        c.execute("SELECT role FROM agents WHERE agent_id=?", (caller_agent,))
        row = c.fetchone(); d.close()
        if row and row[0] == 'executor':
            raise HTTPException(403, "workers may not attach jobs to intents")

    d = db(); c = d.cursor()
    attached = []
    for jid in job_ids:
        c.execute("SELECT 1 FROM exo_jobs WHERE job_id=?", (jid,))
        if c.fetchone():
            c.execute("INSERT OR IGNORE INTO intent_jobs (intent_id, job_id) VALUES (?, ?)", (intent_id, jid))
            c.execute("UPDATE exo_jobs SET intent_id=? WHERE job_id=?", (intent_id, jid))
            attached.append(jid)
    d.commit()
    append_intent_narrative(intent_id, f"Attached {len(attached)} jobs: {attached}")
    d.close()
    return {"intent_id": intent_id, "attached_jobs": attached}


def issue_job_for_intent(lease_id: str, task_id: str, agent_id: Optional[str], intent_id: str):
    """Create a job linked to an intent. Returns (job_id, chosen_agent)"""
    chosen_agent = agent_id
    if not chosen_agent:
        chosen_agent = pick_least_busy_worker()
    job_id = str(uuid.uuid4())
    issued_at = utcnow_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    d = db(); c = d.cursor()
    c.execute(
        "INSERT INTO exo_jobs (job_id, agent_id, lease_id, task_id, status, issued_at, expires_at, intent_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (job_id, chosen_agent, lease_id, task_id, "ISSUED", issued_at, expires_at, intent_id)
    )
    d.commit()

    # governance + immutable assignment event
    log_governance_event("Task Issued (intent)", {"job_id": job_id, "agent_id": chosen_agent, "task_id": task_id, "intent_id": intent_id})
    try:
        ts = utcnow_iso()
        c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
        prev = c.fetchone(); prev_hash = prev[0] if prev else ""
        payload = json.dumps({"job_id": job_id, "agent_id": chosen_agent, "lease_id": lease_id, "task_id": task_id, "intent_id": intent_id})
        h = hash_chain(prev_hash, ts, chosen_agent or "SYSTEM", "TASK_ASSIGN", payload)
        c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, chosen_agent or "SYSTEM", "TASK_ASSIGN", payload, prev_hash, h))
        d.commit()
    except Exception:
        pass
    d.close()
    return job_id, chosen_agent

@app.get("/task/status/{job_id}")
def task_status(job_id: str):
    d = db(); c = d.cursor()
    c.execute("SELECT job_id, agent_id, lease_id, task_id, status, issued_at, expires_at, completed_at, receipt FROM exo_jobs WHERE job_id=?", (job_id,))
    row = c.fetchone(); d.close()
    if not row:
        raise HTTPException(404, "job not found")
    return {"job_id": row[0], "agent_id": row[1], "lease_id": row[2], "task_id": row[3], "status": row[4], "issued_at": row[5], "expires_at": row[6], "completed_at": row[7], "receipt": row[8]}

# Task runner API: worker polls for next job and reports updates
@app.get("/task/next")
def task_next(agent_id: str):
    """Return a single ISSUED job for the agent and atomically mark it RUNNING."""
    d = db(); c = d.cursor()
    c.execute("SELECT job_id, agent_id, lease_id, task_id, status, issued_at, expires_at FROM exo_jobs WHERE status='ISSUED' AND agent_id=? ORDER BY issued_at LIMIT 1", (agent_id,))
    row = c.fetchone()
    if not row:
        d.close(); return JSONResponse(status_code=204, content={})
    job_id = row[0]
    started = utcnow_iso()
    c.execute("UPDATE exo_jobs SET status='RUNNING', started_at=? WHERE job_id=?", (started, job_id))
    d.commit(); d.close()
    log_governance_event("Task Running", {"job_id": job_id, "agent_id": agent_id, "started_at": started})
    return {"job_id": job_id, "agent_id": row[1], "lease_id": row[2], "task_id": row[3], "status": "RUNNING", "issued_at": row[5], "expires_at": row[6], "started_at": started}

@app.post("/task/update")
def task_update(body: dict):
    """Worker calls this to update job status (RUNNING -> COMPLETED or FAILED).

    Body: { job_id, agent_id, status, receipt (optional) }
    """
    job_id = body.get("job_id"); agent_id = body.get("agent_id"); status = body.get("status"); receipt = body.get("receipt")
    if not job_id or not agent_id or not status:
        raise HTTPException(400, "job_id, agent_id, status required")

    d = db(); c = d.cursor()
    c.execute("SELECT agent_id, lease_id, status FROM exo_jobs WHERE job_id=?", (job_id,))
    row = c.fetchone()
    if not row:
        d.close(); raise HTTPException(404, "job not found")
    if row[0] != agent_id:
        d.close(); raise HTTPException(403, "agent mismatch")

    # Update status and set completion metadata
    completed_at = None
    if status in ("COMPLETED", "FAILED"):
        completed_at = utcnow_iso()
        c.execute("UPDATE exo_jobs SET status=?, completed_at=?, receipt=? WHERE job_id=?", (status, completed_at, receipt, job_id))
    else:
        c.execute("UPDATE exo_jobs SET status=?, receipt=? WHERE job_id=?", (status, receipt, job_id))
    d.commit()

    # Emit a governance event and an audit event (linking lease)
    lease_id = row[1]
    log_governance_event("Task %s" % status, {"job_id": job_id, "agent_id": agent_id, "lease_id": lease_id, "receipt": receipt or ""})

    # Append to events ledger for immutable audit with lease linkage
    try:
        ts = utcnow_iso()
        c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
        prev = c.fetchone()
        prev_hash = prev[0] if prev else ""
        payload = json.dumps({"job_id": job_id, "agent_id": agent_id, "lease_id": lease_id, "status": status, "receipt": receipt})
        h = hash_chain(prev_hash, ts, agent_id, "TASK_UPDATE", payload)
        c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, agent_id, "TASK_UPDATE", payload, prev_hash, h))
        d.commit()
    except Exception:
        pass

    d.close()
    return {"ok": True}

@app.post("/lease/complete")
def lease_complete(res: LeaseComplete):
    log_event({
        "agent_id": res.agent_id,
        "lease_id": res.lease_id,
        "type": "LEASE_CLOSED_START",
        "payload": f"Lease {res.lease_id} completion initiated."
    })
    require_active_lease(res.lease_id, agent_id=res.agent_id)
    final_state = "COMPLETED" if res.success else "FAILED"
    d = db(); c = d.cursor()
    c.execute("UPDATE leases SET state=? WHERE lease_id=? AND agent_id=? AND state='ACTIVE'", (final_state, res.lease_id, res.agent_id))
    c.execute("DELETE FROM lease_consumers WHERE lease_id=?", (res.lease_id,))
    d.commit(); d.close()
    return {"status": "CLOSED", "final_state": final_state}

# =========================================================
# Step 7: Federation & Hardened Node Admission
# =========================================================

def _verify_node_sig(node_id: str, pubkey: str, message: str, signature_b64: str) -> bool:
    if not REQUIRE_SIGNATURES: return True
    if not _CRYPTO_OK: return False
    try:
        keydata = base64.b64decode(pubkey.split()[1].encode())
        def read_u32(b, off): return int.from_bytes(b[off:off+4], "big"), off+4
        def read_str(b, off):
            ln, off = read_u32(b, off)
            return b[off:off+ln], off+ln
        off = 0; t, off = read_str(keydata, off); k, off = read_str(keydata, off)
        pk = Ed25519PublicKey.from_public_bytes(k)
        sig = base64.b64decode(signature_b64.encode())
        pk.verify(sig, message.encode()); return True
    except: return False

@app.post("/node/register")
def node_register(req: SignedNodeRegister):
    now = int(time.time())
    d = db(); c = d.cursor()

    # --- revocation check ---
    c.execute("SELECT revoked FROM remote_nodes WHERE node_id=?", (req.payload.node_id,))
    row = c.fetchone()
    if row and row[0]:
        d.close(); raise HTTPException(403, "node is revoked")
    
    # --- capability allow-list ---
    caps = set(req.payload.capabilities)
    if not caps.issubset(ALLOWED_NODE_CAPABILITIES):
        d.close(); raise HTTPException(403, "invalid capability set")

    # --- replay protection ---
    c.execute("SELECT 1 FROM federation_nonces WHERE nonce=?", (req.nonce,))
    if c.fetchone():
        d.close(); raise HTTPException(409, "replay detected")

    # --- freshness window ---
    if abs(now - req.timestamp) > 120:
        d.close(); raise HTTPException(401, "stale registration")

    # --- signature verification ---
    msg = (
        req.payload.node_id +
        "|" + ",".join(sorted(req.payload.capabilities)) +
        "|" + req.nonce +
        "|" + str(req.timestamp)
    )

    if not _verify_node_sig(req.payload.node_id, req.payload.pubkey, msg, req.signature):
        d.close(); raise HTTPException(403, "invalid node signature")

    # --- mark nonce used ---
    c.execute("INSERT INTO federation_nonces VALUES (?, ?)", (req.nonce, now))

    caps_str = ",".join(req.payload.capabilities)
    c.execute("""
        INSERT OR REPLACE INTO remote_nodes 
        (node_id, pubkey, capabilities, last_seen, status, revoked) 
        VALUES (?, ?, ?, ?, ?, (SELECT revoked FROM remote_nodes WHERE node_id=?) OR 0)
    """, (req.payload.node_id, req.payload.pubkey, caps_str, utcnow_iso(), "ONLINE", req.payload.node_id))
    
    d.commit(); d.close()
    log_governance_event("Node Admitted", {
        "node_id": req.payload.node_id,
        "capabilities": caps_str
    })
    return {"status": "REGISTERED", "node_id": req.payload.node_id}

@app.get("/nodes")
def list_nodes():
    d = db(); c = d.cursor()
    c.execute("SELECT node_id, capabilities, last_seen, status, revoked FROM remote_nodes")
    rows = c.fetchall(); d.close()
    return [{"node_id": r[0], "capabilities": r[1].split(","), "last_seen": r[2], "status": r[3], "revoked": bool(r[4])} for r in rows]

# Invariant (Tier 12):
# A lease in ACTIVE state may be bound to at most one node (exclusive).
# All execution authority flows through federation_authorize.
#
# Invariant (Tier 13):
# A lease is valid only within its declared temporal window [not_before, not_after].
# Temporal validity is enforced at request, execution, and federation layers.
@app.post("/federation/authorize")
def federation_authorize(req: FederationAuthorize):
    d = db(); c = d.cursor()
    c.execute("SELECT pubkey, revoked FROM remote_nodes WHERE node_id=?", (req.node_id,))
    row = c.fetchone(); d.close()
    if not row: raise HTTPException(403, "unknown node")
    if row[1]: raise HTTPException(403, "node is revoked")
    
    evaluate_policy({"node_id": req.node_id, "agent_id": req.agent_id})
    msg = f"{req.node_id}|{req.agent_id}|{req.lease_id}|{req.resource_type}|{req.resource_id}|{req.permission}|{req.nonce}"
    if not _verify_node_sig(req.node_id, row[0], msg, req.signature):
        raise HTTPException(403, "invalid node signature")

    require_active_lease(req.lease_id, agent_id=req.agent_id)
    require_capability(req.lease_id, "run_task", agent_id=req.agent_id)
    require_resource_access(req.lease_id, req.resource_type, req.resource_id, req.permission, agent_id=req.agent_id)
    
    d = db(); c = d.cursor()
    c.execute("SELECT resource_id FROM lease_resources WHERE lease_id=? AND resource_type='performer' AND permission='execute'", (req.lease_id,))
    affinities = c.fetchall(); d.close()
    if affinities:
        if not any(a[0] == req.node_id for a in affinities):
            raise HTTPException(403, f"lease affinity mismatch")

    # Exclusive binding (Tier 12)
    d = db(); c = d.cursor()
    c.execute("SELECT node_id FROM lease_consumers WHERE lease_id=?", (req.lease_id,))
    consumers = [r[0] for r in c.fetchall()]
    
    if req.node_id in consumers:
        # Idempotent re-authorization
        pass
    else:
        if len(consumers) >= 1:
            d.close()
            log_governance_event("Lease Bind Denied (Exclusive)", {
                "lease_id": req.lease_id, "attempted_node": req.node_id,
                "bound_node": consumers[0], "agent_id": req.agent_id
            })
            raise HTTPException(403, f"exclusive lease already bound to node {consumers[0]}")

        # Bind success
        c.execute("INSERT INTO lease_consumers (lease_id, node_id, bound_at) VALUES (?, ?, ?)",
                  (req.lease_id, req.node_id, utcnow_iso()))
        d.commit()
        log_governance_event("Lease Bound (Exclusive)", {
            "lease_id": req.lease_id, "node_id": req.node_id, "agent_id": req.agent_id
        })
    d.close()

    log_governance_event("Scheduling Authorized", {
        "lease_id": req.lease_id,
        "node_id": req.node_id,
        "agent_id": req.agent_id,
        "resource": f"{req.resource_type}:{req.resource_id}"
    })
    return {"status": "AUTHORIZED", "node_id": req.node_id, "agent_id": req.agent_id, "lease_id": req.lease_id}
@app.post("/node/heartbeat")
def node_heartbeat(req: SignedHeartbeat):
    node_id = req.payload.get("node_id")
    if not node_id:
        raise HTTPException(400, "node_id required")

    now = int(time.time())
    d = db(); c = d.cursor()

    # --- revocation check ---
    c.execute("SELECT revoked FROM remote_nodes WHERE node_id=?", (node_id,))
    row = c.fetchone()
    if row and row[0]:
        d.close(); raise HTTPException(403, "node is revoked")

    # freshness
    if abs(now - req.timestamp) > 120:
        d.close(); raise HTTPException(401, "stale heartbeat")

    # replay protection
    c.execute("SELECT 1 FROM heartbeat_nonces WHERE nonce=?", (req.nonce,))
    if c.fetchone():
        d.close()
        raise HTTPException(409, "replay detected")

    # lookup node
    c.execute("SELECT pubkey FROM remote_nodes WHERE node_id=?", (node_id,))
    row = c.fetchone()
    if not row:
        d.close()
        raise HTTPException(403, "unknown node")

    pubkey = row[0]

    # verify signature
    msg = f"{node_id}|{req.nonce}|{req.timestamp}"
    if not _verify_node_sig(node_id, pubkey, msg, req.signature):
        d.close()
        raise HTTPException(403, "invalid node signature")

    # mark nonce used
    c.execute(
        "INSERT INTO heartbeat_nonces VALUES (?, ?)",
        (req.nonce, now)
    )

    # update liveness
    c.execute("""
        UPDATE remote_nodes
        SET last_seen=?, status='ONLINE'
        WHERE node_id=?
    """, (utcnow_iso(), node_id))

    d.commit(); d.close()
    return {"status": "OK", "node_id": node_id}

@app.post("/admin/node/revoke")
def node_revoke(req: NodeRevoke, request: Request):
    agent_id = request.headers.get("X-Agent-ID")
    if not agent_id: raise HTTPException(403, "X-Agent-ID required")
    
    msg = f"REVOKE|{req.target_node_id}|{req.reason}|{req.nonce}"
    require_admin(agent_id, msg, req.signature)
    
    d = db(); c = d.cursor()
    c.execute("UPDATE remote_nodes SET revoked=1, status='REVOKED' WHERE node_id=?", (req.target_node_id,))
    d.commit(); d.close()
    
    return {"status": "REVOKED", "node_id": req.target_node_id}

@app.post("/admin/lease/revoke")
def lease_revoke(req: LeaseRevoke, request: Request):
    agent_id = request.headers.get("X-Agent-ID")
    if not agent_id: raise HTTPException(403, "X-Agent-ID required")
    
    msg = f"LEASE_REVOKE|{req.lease_id}|{req.reason}|{req.nonce}"
    require_admin(agent_id, msg, req.signature)
    
    d = db(); c = d.cursor()
    c.execute("SELECT agent_id FROM leases WHERE lease_id=?", (req.lease_id,))
    row = c.fetchone()
    if not row:
        d.close(); raise HTTPException(404, "lease not found")
    
    d.close()
    revoke_lease_tree(req.lease_id)
    
    log_governance_event("Lease Revoked", {
        "lease_id": req.lease_id,
        "reason": req.reason,
        "revoked_by": agent_id
    })
    
    return {"status": "REVOKED", "lease_id": req.lease_id}

@app.post("/admin/policy/update")
def policy_update(req: PolicyUpdate, request: Request):
    agent_id = request.headers.get("X-Agent-ID")
    if not agent_id: raise HTTPException(403, "X-Agent-ID required")
    
    # Deterministic JSON for signature
    rules_dict = req.rules.dict(exclude_none=True)
    rules_json = json.dumps(rules_dict, sort_keys=True, separators=(",", ":"))
    msg = f"POLICY|{req.policy_id}|{rules_json}|{req.nonce}"
    require_admin(agent_id, msg, req.signature)
    
    d = db(); c = d.cursor()
    c.execute("SELECT version FROM policies WHERE policy_id=?", (req.policy_id,))
    row = c.fetchone()
    version = (row[0] + 1) if row else 1
    
    c.execute("""
        INSERT OR REPLACE INTO policies (policy_id, version, rules, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (req.policy_id, version, rules_json, "ACTIVE", utcnow_iso()))
    d.commit(); d.close()
    log_governance_event("Policy Updated", {
        "policy_id": req.policy_id,
        "version": version,
        "updated_by": agent_id,
        "rules": rules_json
    })
    write_policy_registry()
    
    return {"status": "UPDATED", "policy_id": req.policy_id, "version": version}

# ================= ========================================
# Sweepers & Monitors
# =========================================================

async def lease_sweeper():
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            d = sqlite3.connect(DB_PATH); c = d.cursor()
            c.execute("SELECT lease_id, agent_id FROM leases WHERE state='ACTIVE' AND expires_at < ?", (now,))
            expired = c.fetchall()
            if expired:
                for lid, aid in expired:
                    c.execute("UPDATE leases SET state='EXPIRED' WHERE lease_id=?", (lid,))
                    ts = datetime.now(timezone.utc).isoformat()
                    c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
                    prev = c.fetchone(); prev_hash = prev[0] if prev else ""
                    payload = f"System auto-expired ghost lease {lid} for agent {aid}"
                    h = hashlib.sha256()
                    h.update((prev_hash or "").encode())
                    h.update(ts.encode()); h.update("SYSTEM".encode())
                    h.update("LEASE_AUTO_EXPIRE".encode()); h.update(payload.encode())
                    res_h = h.hexdigest()
                    c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", 
                              (ts, "SYSTEM", "LEASE_AUTO_EXPIRE", payload, prev_hash, res_h))
                d.commit()
            d.close()
        except Exception: pass
        await asyncio.sleep(60)

async def node_decay_monitor():
    while True:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
            d = sqlite3.connect(DB_PATH); c = d.cursor()
            c.execute("""
                UPDATE remote_nodes
                SET status='STALE'
                WHERE last_seen < ? AND status='ONLINE' AND revoked=0
            """, (cutoff.isoformat(),))
            d.commit(); d.close()
        except Exception:
            pass
        await asyncio.sleep(10)

async def agent_decay_monitor():
    """Mark agents STALE when they haven't heartbeat recently."""
    while True:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
            d = sqlite3.connect(DB_PATH); c = d.cursor()
            c.execute("""
                UPDATE agents
                SET status='STALE'
                WHERE last_seen < ? AND status='ONLINE' AND revoked=0
            """, (cutoff.isoformat(),))
            d.commit(); d.close()
        except Exception:
            pass
        await asyncio.sleep(10)

# Failover: single-pass implementation callable from tests
AGENT_STALE_SECONDS = int(os.environ.get("CT_AGENT_STALE_SECONDS", "30"))
JOB_RUNNING_TIMEOUT_SECONDS = int(os.environ.get("CT_JOB_RUNNING_TIMEOUT_SECONDS", "60"))

def normalize_agent_roles():
    """Normalize legacy agent roles to the canonical 'executor' role.

    Idempotent: converts any agent with role 'worker' to 'executor'.
    """
    d = db(); c = d.cursor()
    try:
        c.execute("UPDATE agents SET role='executor' WHERE role='worker'")
        d.commit()
    except Exception:
        pass
    finally:
        d.close()


def ensure_failover_schema():
    """Add any missing columns needed for failover if the DB was not migrated at startup."""
    d = db(); c = d.cursor()
    try:
        c.execute("PRAGMA table_info(exo_jobs)")
        cols = [r[1] for r in c.fetchall()]
        if 'started_at' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN started_at TEXT")
        if 'attempts' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN attempts INTEGER DEFAULT 0")
        if 'intent_id' not in cols:
            c.execute("ALTER TABLE exo_jobs ADD COLUMN intent_id TEXT")

        c.execute("PRAGMA table_info(agents)")
        acols = [r[1] for r in c.fetchall()]
        if 'last_seen' not in acols:
            c.execute("ALTER TABLE agents ADD COLUMN last_seen TEXT")
        if 'status' not in acols:
            c.execute("ALTER TABLE agents ADD COLUMN status TEXT DEFAULT 'ONLINE'")

        # Ensure intents table exists for existing DBs and has required columns
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intents'")
        if not c.fetchone():
            c.execute("""
            CREATE TABLE IF NOT EXISTS intents (
                intent_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                constraints JSON NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                state TEXT,
                narrative TEXT
            )
            """)
        else:
            c.execute("PRAGMA table_info(intents)")
            icol = [r[1] for r in c.fetchall()]
            if 'state' not in icol:
                c.execute("ALTER TABLE intents ADD COLUMN state TEXT")
            if 'narrative' not in icol:
                c.execute("ALTER TABLE intents ADD COLUMN narrative TEXT")

        # Ensure intent_jobs join table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intent_jobs'")
        if not c.fetchone():
            c.execute("""
            CREATE TABLE IF NOT EXISTS intent_jobs (
                intent_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                PRIMARY KEY (intent_id, job_id)
            )
            """)

        d.commit()
    except Exception:
        pass
    finally:
        d.close()


def failover_once(timeout_seconds: int = JOB_RUNNING_TIMEOUT_SECONDS):
    """Perform a single pass of failover: reclaim RUNNING jobs that appear stuck/dead and reassign.

    Returns: list of job_ids reassigned
    """
    # Ensure schema is present even if migration didn't run at startup
    ensure_failover_schema()

    reassigned = []
    now = datetime.now(timezone.utc)
    d = db(); c = d.cursor()
    try:
        c.execute("SELECT job_id, agent_id, started_at FROM exo_jobs WHERE status='RUNNING' AND started_at IS NOT NULL")
        rows = c.fetchall()
        for job_id, agent_id, started_at in rows:
            if not started_at:
                continue
            try:
                started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            except Exception:
                # malformed timestamp; consider it timed out
                started_dt = datetime.fromtimestamp(0, tz=timezone.utc)

            age = (now - started_dt).total_seconds()
            if age < timeout_seconds:
                continue

            # check agent liveness
            c.execute("SELECT last_seen, status FROM agents WHERE agent_id=?", (agent_id,))
            row = c.fetchone()
            stale = True
            if row and row[0]:
                try:
                    last_dt = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
                    stale = (now - last_dt).total_seconds() > AGENT_STALE_SECONDS
                except Exception:
                    stale = True

            # If agent is stale or job timed out, try to reassign
            if stale or age >= timeout_seconds:
                new_agent = pick_least_busy_worker(exclude_agent=agent_id)
                ts = utcnow_iso()
                c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
                prev = c.fetchone(); prev_hash = prev[0] if prev else ""
                payload = json.dumps({"job_id": job_id, "from_agent": agent_id, "to_agent": new_agent})
                h = hash_chain(prev_hash, ts, (new_agent or "SYSTEM"), "TASK_REASSIGN", payload)

                if new_agent:
                    # reassign to another agent and mark ISSUED
                    c.execute(
                        "UPDATE exo_jobs SET agent_id=?, status='ISSUED', started_at=NULL, attempts=COALESCE(attempts,0)+1 WHERE job_id=?",
                        (new_agent, job_id)
                    )
                    c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, new_agent, "TASK_REASSIGN", payload, prev_hash, h))
                    reassigned.append(job_id)
                else:
                    # no eligible worker: clear assignment and mark ISSUED so operator can re-issue
                    c.execute("UPDATE exo_jobs SET agent_id=NULL, status='ISSUED', started_at=NULL WHERE job_id=?", (job_id,))
                    c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, "SYSTEM", "TASK_REASSIGN", payload, prev_hash, h))
                    reassigned.append(job_id)

        d.commit()
    except Exception:
        pass
    finally:
        d.close()
    return reassigned

async def failover_sweeper():
    while True:
        try:
            failover_once()
        except Exception:
            pass
        await asyncio.sleep(10)

@app.post("/admin/failover/once")
def admin_failover_once(request: Request):
    """Admin endpoint to trigger a single failover pass. Requires admin agent."""
    agent_id = request.headers.get("X-Agent-ID")
    if not agent_id:
        raise HTTPException(403, "X-Agent-ID required")
    d = db(); c = d.cursor()
    c.execute("SELECT role FROM agents WHERE agent_id=?", (agent_id,))
    row = c.fetchone(); d.close()
    if not row or row[0] != 'admin':
        raise HTTPException(403, "admin role required")

    reassigned = failover_once()
    return {"reassigned": reassigned}


def append_intent_narrative(intent_id: str, text: str):
    """Append a narrative line to the intent and write an Obsidian note."""
    d = db(); c = d.cursor()
    try:
        ts = utcnow_iso()
        note_line = f"{ts} - {text}\n"
        c.execute("SELECT narrative FROM intents WHERE intent_id=?", (intent_id,))
        row = c.fetchone()
        old = row[0] if row and row[0] else ""
        new = old + note_line
        c.execute("UPDATE intents SET narrative=? WHERE intent_id=?", (new, intent_id))
        d.commit()
        # write to Obsidian intent note
        try:
            path = os.path.join(OBSIDIAN_PATH, "SYSTEM", "Intents")
            os.makedirs(path, exist_ok=True)
            fname = os.path.join(path, f"intent-{intent_id}.md")
            # load current intent state/title
            c.execute("SELECT description, state, created_at, completed_at FROM intents WHERE intent_id=?", (intent_id,))
            idesc = c.fetchone()
            desc_str = idesc[0] if idesc else ""
            state_str = idesc[1] if idesc and idesc[1] else ""
            created_at = idesc[2] if idesc else ""
            completed_at = idesc[3] if idesc else ""
            with open(fname, "w") as f:
                f.write(f"# Intent: {desc_str}\n\n")
                f.write(f"Created: {created_at}\n")
                f.write(f"State: {state_str}\n")
                if completed_at:
                    f.write(f"Completed: {completed_at}\n")
                f.write("\n## Narrative\n\n")
                f.write(new)
        except Exception:
            pass
    except Exception:
        pass
    finally:
        d.close()


def intent_observer_once():
    """Compute intent states from job states and append narrative. This NEVER mutates jobs."""
    changed = []
    d = db(); c = d.cursor()
    try:
        c.execute("SELECT intent_id, description, constraints, state FROM intents")
        intents = c.fetchall()
        for intent_id, desc, constraints_json, state in intents:
            # compute counts
            c.execute("SELECT COUNT(*), SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END), SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END), SUM(CASE WHEN status IN ('ISSUED','RUNNING') THEN 1 ELSE 0 END) FROM exo_jobs WHERE intent_id=?", (intent_id,))
            total, completed, failed, outstanding = c.fetchone()
            total = total or 0
            completed = completed or 0
            failed = failed or 0
            outstanding = outstanding or 0

            new_state = state or 'PENDING'

            if total == 0:
                new_state = 'PENDING'
            elif completed == total and total > 0:
                new_state = 'COMPLETED'
            elif failed > 0 and completed == 0:
                new_state = 'FAILED'
            elif failed > 0 and (completed > 0 or outstanding > 0):
                new_state = 'DEGRADED'
            elif outstanding > 0:
                new_state = 'RUNNING'

            if new_state != state:
                # update state and append narrative and emit event
                c.execute("UPDATE intents SET state=? WHERE intent_id=?", (new_state, intent_id))
                append_intent_narrative(intent_id, f"State changed to {new_state}: total={total}, completed={completed}, failed={failed}, outstanding={outstanding}")
                # ledger event
                ts = utcnow_iso()
                c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
                prev = c.fetchone(); prev_hash = prev[0] if prev else ""
                payload = json.dumps({"intent_id": intent_id, "state": new_state, "total": total, "completed": completed, "failed": failed, "outstanding": outstanding})
                h = hash_chain(prev_hash, ts, "SYSTEM", f"INTENT_{new_state}", payload)
                c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, "SYSTEM", f"INTENT_{new_state}", payload, prev_hash, h))
                # set completed_at if moved to COMPLETED or FAILED
                if new_state in ('COMPLETED', 'FAILED'):
                    c.execute("UPDATE intents SET completed_at=? WHERE intent_id=?", (utcnow_iso(), intent_id))
                changed.append(intent_id)

        # Detect TASK_REASSIGN events that affect intents and append narrative
        c.execute("SELECT id, ts, agent_id, type, payload FROM events WHERE type='TASK_REASSIGN' ORDER BY id DESC LIMIT 50")
        evs = c.fetchall()
        for eid, ets, eagent, etype, payload in evs:
            try:
                p = json.loads(payload)
                jid = p.get('job_id')
                if not jid: continue
                c.execute("SELECT intent_id FROM exo_jobs WHERE job_id=?", (jid,))
                r = c.fetchone()
                if r and r[0]:
                    intent_id = r[0]
                    append_intent_narrative(intent_id, f"Recovery: job {jid} reassigned from {p.get('from_agent')} to {p.get('to_agent')}")
            except Exception:
                pass

        d.commit()
    except Exception:
        pass
    finally:
        d.close()
    return changed

async def intent_observer_sweeper():
    while True:
        try:
            intent_observer_once()
        except Exception:
            pass
        await asyncio.sleep(5)

async def orchestrator_sweeper():
    while True:
        try:
            orchestrator_once()
        except Exception:
            pass
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(lease_sweeper())
    asyncio.create_task(node_decay_monitor())
    asyncio.create_task(agent_decay_monitor())
    asyncio.create_task(failover_sweeper())
    asyncio.create_task(orchestrator_sweeper())
    asyncio.create_task(intent_observer_sweeper())
    # Normalize legacy roles on startup
    try:
        normalize_agent_roles()
    except Exception:
        pass

    # Governance note: Tier 14 is intentionally inactive/guarded until explicitly enabled.
    log_governance_event("Tier 14 Inactive", {"status": "guarded", "note": "delegation disabled"})
# WRITE TEST Wed Jan 14 01:56:47 PM GMT 2026

# =========================================================
# Phase 2 — Observability (Read-Only Endpoints)
# =========================================================

from ct_runtime.core.observability import health, authority, remote_nodes

@app.get("/health")
def health_route():
    return health()

@app.get("/authority")
def authority_route():
    return authority()

@app.get("/federation/nodes")
def federation_nodes_route():
    return remote_nodes()

# =========================================================
# End Observability
# =========================================================
