#!/usr/bin/env python3
import os
import sqlite3
import hashlib
import uuid
import json
import asyncio
import time
import base64
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
    d = sqlite3.connect(DB_PATH)
    c = d.cursor()

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

    seed = [
        ("executor", "run_task"),
        ("executor", "read_models"),
        ("executor", "emit_events"),
        ("executor", "manage_resources"),
        ("writer", "emit_events"),
        ("admin", "manage_federation"),
        ("admin", "manage_policy")
    ]
    c.executemany("INSERT OR IGNORE INTO roles_permissions (role, capability) VALUES (?, ?)", seed)

    c.execute("SELECT COUNT(*) FROM node_identity")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO node_identity VALUES (?, ?, ?, ?)", (NODE_ID, NODE_ROLE, 1, utcnow_iso()))

    d.commit()
    d.close()


init_db()

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
    d = db(); c = d.cursor()
    c.execute("SELECT agent_id, expires_at, state FROM leases WHERE lease_id=?", (lease_id,))
    row = c.fetchone(); d.close()
    if not row: raise HTTPException(403, "invalid lease")
    lease_agent, expires_at, state = row
    if agent_id and lease_agent != agent_id: raise HTTPException(403, "lease not owned by agent")
    if state == "REVOKED":
        raise HTTPException(403, "lease revoked")
    if state != "ACTIVE":
        raise HTTPException(403, f"lease not active ({state})")
    try:
        exp = datetime.fromisoformat(expires_at)
    except Exception:
        raise HTTPException(403, "invalid lease expiry")
    if datetime.now(timezone.utc) > exp:
        d_upd = db(); c_upd = d_upd.cursor()
        c_upd.execute("UPDATE leases SET state='EXPIRED' WHERE lease_id=? AND state='ACTIVE'", (lease_id,))
        d_upd.commit(); d_upd.close()
        raise HTTPException(403, "lease expired")

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

def require_admin(agent_id: str, message: str, signature: str):
    d = db(); c = d.cursor()
    c.execute("SELECT role, revoked FROM agents WHERE agent_id=?", (agent_id,))
    row = c.fetchone(); d.close()
    if not row or row[1] or row[0] != "admin":
        raise HTTPException(403, "admin privileges required")
    if not _verify_ed25519(agent_id, message, signature):
        raise HTTPException(403, "invalid admin signature")

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
    if not agent_id: raise HTTPException(400, "agent_id required")
    d = db(); c = d.cursor()
    c.execute("INSERT OR IGNORE INTO agents (agent_id, role, revoked, created_at) VALUES (?, ?, ?, ?)", (agent_id, "readonly", 0, utcnow_iso()))
    d.commit(); d.close()
    return {"node": NODE_ID, "agent_role": "readonly"}

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
    d = db(); c = d.cursor()
    c.execute("SELECT role, revoked FROM agents WHERE agent_id=?", (req.agent_id,))
    row = c.fetchone()
    if not row or row[1]: d.close(); raise HTTPException(403, "agent invalid/revoked")
    role = row[0]; caps = SCOPE_CAPABILITIES.get(req.scope)
    if caps is None: d.close(); raise HTTPException(400, "unknown scope")
    
    # Policy Check: Capability Ceiling

    # Policy Check: Capability Ceiling
    evaluate_policy({"requested_caps": caps, "agent_id": req.agent_id})
    # Policy Check: Resource Pairing
    if req.resources:
        for r in req.resources:
            if r.type == "performer":
                evaluate_policy({"agent_id": req.agent_id, "node_id": r.id})

    
    for cap in caps:
        c.execute("SELECT 1 FROM roles_permissions WHERE role=? AND capability=?", (role, cap))
        if not c.fetchone(): d.close(); raise HTTPException(403, f"capability denied: {cap}")

    res_str = ""
    if req.resources:
        rs = sorted(req.resources, key=lambda x: f"{x.type}:{x.id}:{x.perm}")
        res_str = "|".join([f"{r.type}:{r.id}:{r.perm}" for r in rs])
    nonce = req.nonce or ""
    msg = f"{req.agent_id}|{req.task_id}|{req.scope}|{res_str}|{nonce}"
    if REQUIRE_SIGNATURES:
        if not req.signature or not _verify_ed25519(req.agent_id, msg, req.signature):
            d.close(); raise HTTPException(403, "bad signature")

    lease_id = str(uuid.uuid4()); issued_at = utcnow_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    lease_hash = hashlib.sha256(f"{lease_id}|{req.task_id}|{msg}".encode()).hexdigest()
    mode = "exclusive"
    max_consumers = 1
    c.execute("""
INSERT INTO leases
(lease_id, task_id, agent_id, scope, issued_at, expires_at, state, prev_hash, hash, mode, max_consumers)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    lease_id,
    req.task_id,
    req.agent_id,
    req.scope,
    issued_at,
    expires_at,
    "ACTIVE",
    None,
    lease_hash,
    mode,
    max_consumers
))
    for cap in caps: c.execute("INSERT INTO lease_capabilities VALUES (?, ?)", (lease_id, cap))
    if req.resources:
        for r in req.resources: c.execute("INSERT INTO lease_resources VALUES (?, ?, ?, ?)", (lease_id, r.type, r.id, r.perm))
    d.commit(); d.close()
    return {"status": "GRANTED", "lease_id": lease_id, "expires_at": expires_at}

@app.post("/event")
def log_event(body: dict):
    agent_id = body.get("agent_id"); lease_id = body.get("lease_id")
    etype = body.get("type", "GENERIC"); payload = body.get("payload", "")
    if not agent_id or not lease_id: raise HTTPException(403, "agent_id/lease_id required")
    require_capability(lease_id, "emit_events", agent_id=agent_id)
    d = db(); c = d.cursor()
    c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1")
    prev = c.fetchone(); prev_hash = prev[0] if prev else ""; ts = utcnow_iso()
    h = hash_chain(prev_hash, ts, agent_id, etype, str(payload))
    c.execute("INSERT INTO events (ts, agent_id, type, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, agent_id, etype, str(payload), prev_hash, h))
    d.commit(); d.close()
    return {"ok": True, "hash": h}

@app.post("/model/call")
def model_call(req: ModelInvoke):
    require_capability(req.lease_id, "run_task", agent_id=req.agent_id)
    require_resource_access(req.lease_id, "model", req.model_id, "invoke", agent_id=req.agent_id)
    return {"status": "success", "model": req.model_id, "response": f"Mock response from {req.model_id}..."}

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

# Invariant:
# A lease in ACTIVE state may be bound to at most one node at any time.
# All execution authority flows through federation_authorize.
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

    # --- TIER 12: EXCLUSIVE BINDING ---
    d = db(); c = d.cursor()
    c.execute("SELECT node_id FROM lease_consumers WHERE lease_id=?", (req.lease_id,))
    binding = c.fetchone()
    if binding:
        if binding[0] != req.node_id:
            d.close()
            log_governance_event("Lease Bind Denied", {
                "lease_id": req.lease_id,
                "attempted_node": req.node_id,
                "bound_node": binding[0],
                "agent_id": req.agent_id
            })
            raise HTTPException(403, f"exclusive lease already bound to node {binding[0]}")
    else:
        c.execute("INSERT INTO lease_consumers (lease_id, node_id, bound_at) VALUES (?, ?, ?)", (req.lease_id, req.node_id, utcnow_iso()))
        d.commit()
        log_governance_event("Lease Bound (Exclusive)", {
            "lease_id": req.lease_id,
            "node_id": req.node_id,
            "agent_id": req.agent_id
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
    
    c.execute("UPDATE leases SET state='REVOKED' WHERE lease_id=?", (req.lease_id,))
    c.execute("DELETE FROM lease_consumers WHERE lease_id=?", (req.lease_id,))
    d.commit(); d.close()
    
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

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(lease_sweeper())
    asyncio.create_task(node_decay_monitor())
