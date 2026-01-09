import urllib.request
import json
import base64
import time
from cryptography.hazmat.primitives.asymmetric import ed25519

# Configuration
URL = "http://127.0.0.1:7777"

def request(path, data=None):
    req = urllib.request.Request(URL + path, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    try:
        body = json.dumps(data).encode() if data else None
        with urllib.request.urlopen(req, data=body) as r:
            return json.loads(r.read()), r.getcode()
    except Exception as e:
        if hasattr(e, 'read'):
            return e.read().decode(), e.getcode()
        return str(e), 500

def get_signed_reg(sk, node_id, caps):
    ts = int(time.time())
    nonce = f"n-{node_id}-{ts}"
    payload = {"node_id": node_id, "pubkey": None, "capabilities": caps}
    # Identity public key used in server side is OpenSSH format based on how we generated it before
    # But here we just need to provide it to the signer.
    # We'll use the same helper as before to get the OpenSSH pubkey string.
    pk = sk.public_key()
    pub_str = f"ssh-ed25519 {base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00 ' + pk.public_bytes_raw()).decode()} {node_id}"
    payload["pubkey"] = pub_str
    
    msg = f"{node_id}|{','.join(sorted(caps))}|{nonce}|{ts}"
    sig = base64.b64encode(sk.sign(msg.encode())).decode()
    return {
        "payload": payload,
        "nonce": nonce,
        "timestamp": ts,
        "signature": sig
    }

# 1. Generate Node Keys
sk_node_a = ed25519.Ed25519PrivateKey.generate()
sk_node_b = ed25519.Ed25519PrivateKey.generate()

# 2. Register Nodes
print("\n--- Step 1: Register Node A & B (Hardened) ---")
resp, code = request("/node/register", get_signed_reg(sk_node_a, "node-a", ["model_host"]))
print(f"Node A: {code}, {resp}")
resp, code = request("/node/register", get_signed_reg(sk_node_b, "node-b", ["model_host"]))
print(f"Node B: {code}, {resp}")

# 3. Request Lease with Affinity for Node A
print("\n--- Step 2: Request Lease with Affinity to Node A ---")
sk_agent = ed25519.Ed25519PrivateKey.generate()
pk_agent = sk_agent.public_key()
pub_agent = f"ssh-ed25519 {base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00 ' + pk_agent.public_bytes_raw()).decode()} agent-1"
request("/admin/register_key", {"agent_id": "agent-1", "pubkey": pub_agent})
request("/agent/hello", {"agent_id": "agent-1"})

import sqlite3; import os
d = sqlite3.connect(os.path.expanduser("~/invictus/data/ct_memory.db"))
d.execute("UPDATE agents SET role='executor' WHERE agent_id='agent-1'")
d.commit(); d.close()

nonce_l = str(int(time.time()))
msg_l = f"agent-1|task-aff|full|model:llama3:invoke|performer:node-a:execute|{nonce_l}"
sig_l = base64.b64encode(sk_agent.sign(msg_l.encode())).decode()

lease_req = {
    "agent_id": "agent-1", "task_id": "task-aff", "scope": "full",
    "resources": [
        {"type": "model", "id": "llama3", "perm": "invoke"},
        {"type": "performer", "id": "node-a", "perm": "execute"}
    ],
    "nonce": nonce_l, "signature": sig_l
}
resp, code = request("/lease/request", lease_req)
LEASE_ID = resp.get("lease_id")
print(f"Lease Response: {code}, {LEASE_ID}")

# 4. Federation Authorize
print("\n--- Step 3: Authorize on Node A (Valid) ---")
nonce_node = "n1"
msg_node = f"node-a|agent-1|{LEASE_ID}|model|llama3|invoke|{nonce_node}"
sig_node = base64.b64encode(sk_node_a.sign(msg_node.encode())).decode()
body_auth = {
    "node_id": "node-a", "agent_id": "agent-1", "lease_id": LEASE_ID,
    "resource_type": "model", "resource_id": "llama3", "permission": "invoke",
    "nonce": nonce_node, "signature": sig_node
}
resp, code = request("/federation/authorize", body_auth)
print(f"Node A Auth: {code}, {resp}")

print("\n--- Step 4: Replay Attempt (Node A Re-registration) ---")
reg_a = get_signed_reg(sk_node_a, "node-a", ["model_host"])
resp, code = request("/node/register", reg_a)
print(f"Original: {code}")
resp, code = request("/node/register", reg_a)
print(f"Replay: {code}, {resp}")

print("\n--- Step 5: Capability Violation (Unauthorized Capability) ---")
bad_reg = get_signed_reg(sk_node_a, "node-a", ["root_access"])
resp, code = request("/node/register", bad_reg)
print(f"Bad Cap: {code}, {resp}")
