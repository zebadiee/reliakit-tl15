import os
import time
import base64
import json
import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

URL = "http://127.0.0.1:7777"
ADMIN_ID = "admin-gov-v2"
TEST_AGENT = "test-agent-v2"

# 1. Generate Admin Key
admin_priv = Ed25519PrivateKey.generate()
admin_pub = admin_priv.public_key()
pub_bytes = admin_pub.public_bytes(
    encoding=serialization.Encoding.OpenSSH,
    format=serialization.PublicFormat.OpenSSH
).decode()

def sign_msg(priv, msg):
    sig = priv.sign(msg.encode())
    return base64.b64encode(sig).decode()

# 2. Setup Agents
print("--- [1] Setting up Agents ---")
requests.post(f"{URL}/agent/hello", json={"agent_id": ADMIN_ID})
requests.post(f"{URL}/agent/hello", json={"agent_id": TEST_AGENT})
requests.post(f"{URL}/admin/register_key", json={"agent_id": ADMIN_ID, "pubkey": pub_bytes})

# Elevate Admin manually in DB
import sqlite3
DB_PATH = os.path.expanduser("~/invictus/data/ct_memory.db")
conn = sqlite3.connect(DB_PATH)
conn.execute("UPDATE agents SET role='admin' WHERE agent_id=?", (ADMIN_ID,))
conn.execute("UPDATE agents SET role='executor' WHERE agent_id=?", (TEST_AGENT,))
conn.commit()
conn.close()

# 3. Create a Policy: Capability Ceiling
print("\n--- [2] Applying Capability Ceiling Policy (Restrict to 'run_task') ---")
policy_id = "global-ceiling"
rules = {
    "capability_ceiling": ["run_task"]
}
rules_json = json.dumps(rules, sort_keys=True, separators=(',', ':'))
nonce = f"nonce-pol-v2-{int(time.time())}"
msg = f"POLICY|{policy_id}|{rules_json}|{nonce}"
sig = sign_msg(admin_priv, msg)

resp = requests.post(f"{URL}/admin/policy/update", json={
    "policy_id": policy_id,
    "rules": rules,
    "nonce": nonce,
    "signature": sig
}, headers={"X-Agent-ID": ADMIN_ID})
print(f"Policy Update Status: {resp.status_code} {resp.json() if resp.status_code == 200 else resp.text}")

# 4. Test Violation: Request 'full' scope
print("\n--- [3] Testing Violation: Requesting 'full' scope (violates ceiling) ---")
# 'full' scope includes 'read_models' which is NOT in the ceiling
lease_req = {
    "agent_id": TEST_AGENT,
    "task_id": "task-violator",
    "scope": "full"
}
resp = requests.post(f"{URL}/lease/request", json=lease_req)
print(f"Lease Request Result (Violator): {resp.status_code} {resp.text}")

# 5. Test Success: Request 'run' scope
print("\n--- [4] Testing Success: Requesting 'run' scope (obeys ceiling) ---")
lease_req = {
    "agent_id": TEST_AGENT,
    "task_id": "task-compliant",
    "scope": "run"
}
resp = requests.post(f"{URL}/lease/request", json=lease_req)
print(f"Lease Request Result (Compliant): {resp.status_code} {resp.json() if resp.status_code == 200 else resp.text}")
