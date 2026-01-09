import urllib.request
import json
import base64
import time
from cryptography.hazmat.primitives.asymmetric import ed25519

URL = "http://127.0.0.1:7777"

def request(path, data=None):
    req = urllib.request.Request(URL + path, method="POST" if data else "GET")
    req.add_header("Content-Type", "application/json")
    try:
        body = json.dumps(data).encode() if data else None
        with urllib.request.urlopen(req, data=body) as r:
            return json.loads(r.read()), r.getcode()
    except Exception as e:
        if hasattr(e, 'read'): return e.read().decode(), e.getcode()
        return str(e), 500

def get_signed_reg(sk, node_id, caps):
    ts = int(time.time()); nonce = f"n-reg-{node_id}-{ts}"
    pk = sk.public_key()
    pub_str = f"ssh-ed25519 {base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00 ' + pk.public_bytes_raw()).decode()} {node_id}"
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

# 1. Setup
sk = ed25519.Ed25519PrivateKey.generate()
node_id = "node-heartbeat-test"

print("\n--- Step 1: Register Node ---")
resp, code = request("/node/register", get_signed_reg(sk, node_id, ["model_host"]))
print(f"Register: {code}, {resp}")

print("\n--- Step 2: Send Valid Heartbeat ---")
resp, code = request("/node/heartbeat", get_signed_hb(sk, node_id))
print(f"Heartbeat 1: {code}, {resp}")

print("\n--- Step 3: Check Node Status (Wait for sync) ---")
resp, code = request("/nodes")
node = next((n for n in resp if n['node_id'] == node_id), None)
print(f"Status: {node['status']}, Last Seen: {node['last_seen']}")

print("\n--- Step 4: Replay Heartbeat ---")
hb = get_signed_hb(sk, node_id)
request("/node/heartbeat", hb)
resp, code = request("/node/heartbeat", hb)
print(f"Replay Attempt: {code}, {resp}")

print("\n--- Step 5: Test Decay (Simulated) ---")
import sqlite3, os
db = sqlite3.connect(os.path.expanduser("~/invictus/data/ct_memory.db"))
# Backdate last_seen to 2 minutes ago
db.execute("UPDATE remote_nodes SET last_seen='2020-01-01T00:00:00Z' WHERE node_id=?", (node_id,))
db.commit(); db.close()

print("Backdated. Waiting for Monitor (30s skip simulation)...")
# We'll just trigger the monitor logic manually via a script or wait. 
# For verification, we can just run the monitor logic here if we had db access, 
# but the server is running it. We'll wait 35s.
time.sleep(35)
resp, code = request("/nodes")
node = next((n for n in resp if n['node_id'] == node_id), None)
print(f"Decayed Status: {node['status']}")
