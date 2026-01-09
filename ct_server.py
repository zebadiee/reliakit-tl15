#!/usr/bin/env python3
import os
import sqlite3
import hashlib
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

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

app = FastAPI(title="CT Invictus Control Plane")

# Capability mapping
SCOPE_CAPABILITIES = {
    "noop": [],
    "run": ["run_task"],
    "models": ["read_models"],
    "full": ["run_task", "read_models", "emit_events", "manage_resources"],
}

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
        hash TEXT NOT NULL
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

    seed = [
        ("executor", "run_task"),
        ("executor", "read_models"),
        ("executor", "emit_events"),
        ("executor", "manage_resources"),
        ("writer", "emit_events"),
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
    if state != "ACTIVE": raise HTTPException(403, f"lease not active ({state})")
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
    import base64
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
    # Fixed: inserting 9 values to match the DB schema (added None for prev_hash)
    c.execute("INSERT INTO leases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (lease_id, req.task_id, req.agent_id, req.scope, issued_at, expires_at, "ACTIVE", None, lease_hash))
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
    d.commit(); d.close()
    return {"status": "CLOSED", "final_state": final_state}
