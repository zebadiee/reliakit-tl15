import json
import base64
import urllib.request
import sqlite3
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

URL = "http://localhost:7777"
AGENT_ID = "final_tester"
AGENT_ID_2 = "bad_actor"
TASK_ID = "task-final"
SCOPE = "full"

def sign_msg(priv_key, msg):
    return base64.b64encode(priv_key.sign(msg.encode())).decode()

def request(path, payload):
    req = urllib.request.Request(f"{URL}{path}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), 200
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read()), e.code
        except:
            return str(e), e.code

# 0. Setup test agents
pk1 = ed25519.Ed25519PrivateKey.generate()
pub1 = pk1.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()
pk2 = ed25519.Ed25519PrivateKey.generate()
pub2 = pk2.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()

db_path = os.path.expanduser("~/invictus/data/ct_memory.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at) VALUES (?, 'executor', 0, 'now')", (AGENT_ID,))
c.execute("INSERT OR REPLACE INTO agent_keys (agent_id, pubkey, added_at) VALUES (?, ?, 'now')", (AGENT_ID, pub1))
c.execute("INSERT OR REPLACE INTO agents (agent_id, role, revoked, created_at) VALUES (?, 'executor', 0, 'now')", (AGENT_ID_2,))
c.execute("INSERT OR REPLACE INTO agent_keys (agent_id, pubkey, added_at) VALUES (?, ?, 'now')", (AGENT_ID_2, pub2))
conn.commit()
conn.close()

print("--- Step 1: Request Valid Lease ---")
res_str = "model:llama3:invoke"
nonce = "n1"
msg = f"{AGENT_ID}|{TASK_ID}|{SCOPE}|{res_str}|{nonce}"
sig = sign_msg(pk1, msg)
payload = {
    "agent_id": AGENT_ID,
    "task_id": TASK_ID,
    "scope": SCOPE,
    "resources": [{"type": "model", "id": "llama3", "perm": "invoke"}],
    "nonce": nonce,
    "signature": sig
}
resp, code = request("/lease/request", payload)
print(f"Code: {code}, Resp: {resp}")
LEASE_ID = resp.get("lease_id")

print("\n--- Step 2: /model/call llama3 (Valid) ---")
payload = {"agent_id": AGENT_ID, "lease_id": LEASE_ID, "model_id": "llama3", "prompt": "hi"}
resp, code = request("/model/call", payload)
print(f"Code: {code}, Resp: {resp}")

print("\n--- Step 3: /model/call gpt4 (Resource Violation) ---")
payload["model_id"] = "gpt4"
resp, code = request("/model/call", payload)
print(f"Code: {code}, Resp: {resp}")

print("\n--- Step 4: /model/call llama3 (Ownership Violation) ---")
payload["agent_id"] = AGENT_ID_2
payload["model_id"] = "llama3"
resp, code = request("/model/call", payload)
print(f"Code: {code}, Resp: {resp}")

print("\n--- Step 5: /event without lease (Policy Violation) ---")
payload = {"agent_id": AGENT_ID, "type": "TEST", "payload": "leak"}
resp, code = request("/event", payload)
print(f"Code: {code}, Resp: {resp}")

print("\n--- Step 6: /event with scoped lease (Valid) ---")
payload["lease_id"] = LEASE_ID
resp, code = request("/event", payload)
print(f"Code: {code}, Resp: {resp}")

print("\n--- Step 7: /lease/complete (Valid) ---")
payload = {"agent_id": AGENT_ID, "lease_id": LEASE_ID, "success": True}
resp, code = request("/lease/complete", payload)
print(f"Code: {code}, Resp: {resp}")

print("\n--- Step 8: /model/call reuse after complete (State Violation) ---")
payload = {"agent_id": AGENT_ID, "lease_id": LEASE_ID, "model_id": "llama3", "prompt": "hi"}
resp, code = request("/model/call", payload)
print(f"Code: {code}, Resp: {resp}")
