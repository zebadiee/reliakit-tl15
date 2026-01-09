import urllib.request
import json
import base64
import time
from cryptography.hazmat.primitives.asymmetric import ed25519

URL = "http://127.0.0.1:7777"

def request(path, data=None, headers=None):
    req = urllib.request.Request(URL + path, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items(): req.add_header(k, v)
    try:
        body = json.dumps(data).encode() if data else None
        with urllib.request.urlopen(req, data=body) as r:
            return json.loads(r.read()), r.getcode()
    except Exception as e:
        if hasattr(e, 'read'): return e.read().decode(), e.getcode()
        return str(e), 500

def get_ssh_pub(pk, label):
    raw = pk.public_bytes_raw()
    prefix = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00 '
    return f"ssh-ed25519 {base64.b64encode(prefix + raw).decode()} {label}"

def get_signed_reg(sk, node_id, caps):
    ts = int(time.time()); nonce = f"n-reg-{node_id}-{ts}"
    pub_str = get_ssh_pub(sk.public_key(), node_id)
    payload = {"node_id": node_id, "pubkey": pub_str, "capabilities": caps}
    msg = f"{node_id}|{','.join(sorted(caps))}|{nonce}|{ts}"
    sig = base64.b64encode(sk.sign(msg.encode())).decode()
    return {"payload": payload, "nonce": nonce, "timestamp": ts, "signature": sig}

def get_signed_hb(sk, node_id):
    ts = int(time.time()); nonce = f"n-hb-{node_id}-{ts}"
    payload = {"node_id": node_id}
    msg = f"{node_id}|{nonce}|{ts}"
    sig = base64.b64encode(sk.sign(msg.encode())).decode()
    return {"payload": payload, "nonce": nonce, "timestamp": ts, "signature": sig}

# 1. Setup Node and Admin Agent
sk_node = ed25519.Ed25519PrivateKey.generate()
node_id = "evicted-node"

sk_admin = ed25519.Ed25519PrivateKey.generate()
admin_id = "admin-agent"
pub_admin = get_ssh_pub(sk_admin.public_key(), admin_id)

print("\n--- Step 1: Register Node & Admin ---")
request("/node/register", get_signed_reg(sk_node, node_id, ["model_host"]))
request("/admin/register_key", {"agent_id": admin_id, "pubkey": pub_admin})
request("/agent/hello", {"agent_id": admin_id})

import sqlite3, os
db = sqlite3.connect(os.path.expanduser("~/invictus/data/ct_memory.db"))
db.execute("UPDATE agents SET role='admin' WHERE agent_id=?", (admin_id,))
db.commit(); db.close()

# 2. Verify Heartbeat Works
print("\n--- Step 2: Verify Initial Liveness ---")
resp, code = request("/node/heartbeat", get_signed_hb(sk_node, node_id))
print(f"Heartbeat (Pre-Revoke): {code}")

# 3. Revoke Node
print("\n--- Step 3: Revoke Node ---")
nonce_r = "revoke-123"
msg_r = f"REVOKE|{node_id}|hostile actor|{nonce_r}"
sig_r = base64.b64encode(sk_admin.sign(msg_r.encode())).decode()
body_r = {"target_node_id": node_id, "reason": "hostile actor", "nonce": nonce_r, "signature": sig_r}
resp, code = request("/admin/node/revoke", body_r, headers={"X-Agent-ID": admin_id})
print(f"Revoke Result: {code}, {resp}")

# 4. Verify Denied
print("\n--- Step 4: Verify Denied ---")
resp, code = request("/node/heartbeat", get_signed_hb(sk_node, node_id))
print(f"Heartbeat (Post-Revoke): {code}, {resp}")

resp, code = request("/node/register", get_signed_reg(sk_node, node_id, ["model_host"]))
print(f"Re-registration (Post-Revoke): {code}, {resp}")
