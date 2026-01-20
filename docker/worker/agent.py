#!/usr/bin/env python3
import os
import time
import uuid
import socket
import logging
import requests
try:
    import yaml
    _HAS_YAML = True
except Exception:
    import json as yaml  # fallback to json interface
    _HAS_YAML = False

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

AGENT_YAML_PATH = os.environ.get("AGENT_YAML_PATH", "/app/agent.yaml")
CT_HANDSHAKE_URL = os.environ.get("CT_HANDSHAKE_URL", "http://hermes:7778/node/register")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8090"))
AGENT_ROLE = os.environ.get("AGENT_ROLE", "worker")
# Allow override of agent_id via env var for easy multi-worker testing
ENV_AGENT_ID = os.environ.get("AGENT_ID")


def load_agent_config(path):
    with open(path, "r") as f:
        if _HAS_YAML:
            return yaml.safe_load(f)
        else:
            import json
            return json.load(f)


def normalize_handshake_url(url: str) -> str:
    # Accept /agent/register or /node/register or base URL
    if url.endswith("/agent/register"):
        return url.replace("/agent/register", "/node/register")
    if url.endswith("/node/register"):
        return url
    return url.rstrip("/") + "/node/register"


def post_node_register(cfg):
    node_id = cfg.get("node_id") or socket.gethostname()
    payload = {
        "payload": {
            "node_id": node_id,
            # placeholder pubkey (not used unless signatures enforced)
            "pubkey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEXAMPLE",
            "capabilities": cfg.get("capabilities", ["infer"]),
        },
        "nonce": uuid.uuid4().hex,
        "timestamp": int(time.time()),
        "signature": "",
    }

    url = normalize_handshake_url(CT_HANDSHAKE_URL)
    logging.info(f"POST node register -> %s", url)
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logging.info("Node register response: %s", r.json())
        return True
    except Exception as e:
        logging.error("node register failed: %s", e)
        return False


def post_agent_hello(cfg):
    base = normalize_handshake_url(CT_HANDSHAKE_URL).rsplit("/node/register", 1)[0]
    url = base + "/agent/hello"
    # allow env override for agent id to support cloned workers
    agent_id = ENV_AGENT_ID or cfg.get("agent_id") or socket.gethostname()
    body = {"agent_id": agent_id, "role": cfg.get("role", AGENT_ROLE)}
    logging.info(f"POST agent hello -> %s", url)
    try:
        r = requests.post(url, json=body, timeout=10)
        r.raise_for_status()
        logging.info("Agent hello response: %s", r.json())
        return True
    except Exception as e:
        logging.error("agent hello failed: %s", e)
        return False


def post_agent_hello(cfg):
    base = normalize_handshake_url(CT_HANDSHAKE_URL).rsplit("/node/register", 1)[0]
    url = base + "/agent/hello"
    body = {"agent_id": cfg.get("agent_id"), "role": cfg.get("role", AGENT_ROLE)}
    logging.info(f"POST agent hello -> %s", url)
    try:
        r = requests.post(url, json=body, timeout=10)
        r.raise_for_status()
        logging.info("Agent hello response: %s", r.json())
        return True
    except Exception as e:
        logging.error("agent hello failed: %s", e)
        return False


if __name__ == "__main__":
    cfg = load_agent_config(AGENT_YAML_PATH)

    # IMMUTABLE RUNTIME ASSERTS — fail fast if misconfigured
    ROLE = cfg.get("role") or AGENT_ROLE
    assert ROLE == "executor", f"ROLE must be 'executor', got '{ROLE}'"
    assert "/agent/register" not in CT_HANDSHAKE_URL, "Handshake URL must not reference legacy /agent/register"

    # Try node registration (best effort). Do not abort if it fails.
    ok = post_node_register(cfg)
    # Try agent hello (register agent into local tables)
    ok2 = post_agent_hello(cfg)

    from flask import Flask, jsonify
    import threading

    app = Flask(__name__)

    @app.route("/health")
    def health():
        status = {"status": "ok"}
        if not ok:
            status["register"] = "node_failed"
        elif not ok2:
            status["register"] = "agent_failed"
        else:
            status["register"] = "ok"
        return jsonify(status)

    def _safe_exec(cmd: str):
        # Demo-only allowed commands: echo <text>, do-nothing, true
        if cmd is None or cmd == "do-nothing":
            return (0, "")
        if cmd == "true":
            return (0, "ok")
        if cmd.startswith("echo "):
            return (0, cmd[5:])
        return (1, "unsupported command")

    def poller_loop():
        base = normalize_handshake_url(CT_HANDSHAKE_URL).rsplit('/node/register', 1)[0]
        poll_url = base + "/task/next"
        update_url = base + "/task/update"
        while True:
            try:
                r = requests.get(poll_url, params={"agent_id": cfg.get("agent_id")}, timeout=10)
                if r.status_code == 200:
                    job = r.json()
                    job_id = job.get("job_id")
                    logging.info("Picked job %s", job_id)
                    status_code, out = _safe_exec(cfg.get("command", "do-nothing") if cfg.get("command") else job.get("command"))
                    receipt = out or ("exit:" + str(status_code))
                    requests.post(update_url, json={"job_id": job_id, "agent_id": cfg.get("agent_id"), "status": "COMPLETED", "receipt": receipt}, timeout=10)
                time.sleep(2)
            except Exception as e:
                logging.debug("poll error: %s", e)
                time.sleep(2)

    t = threading.Thread(target=poller_loop, daemon=True)
    t.start()

    logging.info("Starting health server on port %s", HEALTH_PORT)
    app.run(host="0.0.0.0", port=HEALTH_PORT)
