#!/usr/bin/env python3

import os
import sqlite3
import hashlib
import uuid
import json
import asyncio
import time
import base64

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse


# =========================================================
# CONFIG (DO NOT CHANGE)
# =========================================================

DB_PATH = "/home/zebadiee/invictus/data/ct_memory.db"
NODE_ID = "invictus"
NODE_ROLE = "authoritative"


# =========================================================
# HELPERS
# =========================================================

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========================================================
# DATABASE INITIALISATION (FINAL)
# =========================================================

def init_db():
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
    CREATE TABLE IF NOT EXISTS roles_permissions (
        role TEXT NOT NULL,
        capability TEXT NOT NULL,
        PRIMARY KEY (role, capability)
    )
    """)

    c.executemany(
        "INSERT OR IGNORE INTO roles_permissions (role, capability) VALUES (?, ?)",
        [
            ("admin", "manage_policy"),
            ("executor", "run_task"),
            ("executor", "emit_events"),
        ]
    )

    c.execute("SELECT COUNT(*) FROM node_identity")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO node_identity VALUES (?, ?, ?, ?)",
            (NODE_ID, NODE_ROLE, 1, utcnow_iso())
        )

    d.commit()
    d.close()


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "online", "node": NODE_ID}


@app.get("/identity")
def identity():
    d = sqlite3.connect(DB_PATH)
    c = d.cursor()
    row = c.execute(
        "SELECT node_id, role, locked, locked_at FROM node_identity"
    ).fetchone()
    d.close()
    return {
        "node_id": row[0],
        "role": row[1],
        "locked": bool(row[2]),
        "locked_at": row[3],
    }


@app.post("/agent/hello")
def agent_hello(body: Dict[str, Any]):
    agent_id = body["agent_id"]
    role = body.get("role", "readonly")

    d = sqlite3.connect(DB_PATH)
    c = d.cursor()

    c.execute(
        "INSERT OR IGNORE INTO agents VALUES (?, ?, 0, ?)",
        (agent_id, role, utcnow_iso())
    )

    d.commit()
    d.close()

    return {"node": NODE_ID, "agent_role": role}
