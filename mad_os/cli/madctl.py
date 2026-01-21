"""madctl — deterministic syscall layer for MAD-OS.

IMPORT-SAFETY RULE:
- No writes, no threads, no network, no env mutation on import.
- All side effects occur only after explicit command invocation.

This module implements a minimal, side-effect-free CLI and the
`pull repos` subcommand which clones/pins repositories in READ_ONLY
mode for archaeology and adapter planning.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from mad_os.core.mode import Mode, resolve_mode
from mad_os.capabilities import registry as capability_registry


# ---- helpers (pure) ---------------------------------------------------------

@dataclass(frozen=True)
class Result:
    ok: bool
    data: Dict[str, Any]


def _print(data: Dict[str, Any], as_json: bool):
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        for k, v in data.items():
            print(f"{k}: {v}")


# ---- command handlers (pure; no side effects here) -------------------------

def cmd_status(env: Dict[str, str]) -> Result:
    mode = resolve_mode(env)
    caps = [c.name for c in capability_registry()]
    return Result(True, {"mode": mode.value, "capabilities": caps, "health": "ok"})


def cmd_list_adapters() -> Result:
    caps = capability_registry()
    return Result(True, {"adapters": [{"name": c.name, "capabilities": getattr(c, "flags", {})} for c in caps]})


def cmd_describe(adapter: str) -> Result:
    # Placeholder: adapters expose describe() later
    return Result(True, {"adapter": adapter, "inputs_schema": "TBD", "explain": True, "enforce": False})


def cmd_explain(adapter: str, input_ref: str) -> Result:
    # Observer-safe placeholder
    return Result(True, {"adapter": adapter, "input": input_ref, "explanation": "EXPLAIN_PLACEHOLDER", "what_would_change": []})


def cmd_run(adapter: str, input_ref: str, scope: str, dry_run: bool, env: Dict[str, str]) -> Result:
    mode = resolve_mode(env)
    if mode != Mode.OPERATOR:
        return Result(False, {"error": "run not permitted", "required_mode": Mode.OPERATOR.value, "current_mode": mode.value})
    return Result(True, {"adapter": adapter, "input": input_ref, "scope": scope, "dry_run": dry_run, "status": "RUN_PLACEHOLDER"})


# ---- pull repos implementation ----------------------------------------------


def _run(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a command using subprocess.run and return CompletedProcess. Non-zero return codes are allowed."""
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _safe_rev_parse(dest: Path) -> str:
    # Try to get HEAD commit; return UNRESOLVED on failure
    res = _run(["git", "-C", str(dest), "rev-parse", "HEAD"])
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    return "UNRESOLVED"


def _safe_branch(dest: Path) -> str:
    res = _run(["git", "-C", str(dest), "branch", "--show-current"])
    if res.returncode == 0:
        return res.stdout.strip()
    return ""


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def cmd_pull_repos(repos: List[str], root: Path, as_json: bool = False) -> Result:
    root = Path(root).expanduser().resolve()
    _ensure_dir(root)
    timestamp = datetime.utcnow().isoformat() + "Z"

    summary: Dict[str, Any] = {}

    for repo in repos:
        name = Path(repo.rstrip("/" )).name
        dest = root / name
        status: Dict[str, Any] = {"repo": repo, "dest": str(dest)}

        try:
            if (dest / ".git").exists():
                # fetch updates only
                res = _run(["git", "-C", str(dest), "fetch", "--all", "--prune"])
                status["fetched"] = res.returncode == 0
            else:
                # clone read-only (no checkout)
                res = _run(["git", "clone", "--no-checkout", repo, str(dest)])
                status["cloned"] = res.returncode == 0

            commit = _safe_rev_parse(dest)
            branch = _safe_branch(dest)

            mad_dir = dest / ".mad_os"
            _ensure_dir(mad_dir)
            snapshot = mad_dir / "SNAPSHOT.txt"
            snapshot.write_text("""
name={name}
repo={repo}
branch={branch}
commit={commit}
pulled_at={pulled_at}
mode=READ_ONLY
""".strip().format(name=name, repo=repo, branch=branch, commit=commit, pulled_at=timestamp))

            status.update({"commit": commit, "branch": branch, "snapshot": str(snapshot)})
            status["ok"] = True
        except Exception as e:
            status.update({"ok": False, "error": str(e)})

        summary[name] = status

    # write audit entry (JSONL) under root/.mad_os/AUDIT.log — append only
    try:
        audit_entry = {
            "ts": timestamp,
            "actor": "madctl",
            "action": "pull.repos",
            "mode": resolve_mode(os.environ).value,
            "repos": [
                {"url": s.get("repo"), "path": s.get("dest"), "commit": s.get("commit")} for s in summary.values()
            ],
            "root": str(root),
        }
        import hashlib
        payload = json.dumps(audit_entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
        audit_entry["sha"] = hashlib.sha256(payload).hexdigest()
        audit_log = Path(root) / ".mad_os" / "AUDIT.log"
        audit_log.parent.mkdir(parents=True, exist_ok=True)
        with audit_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(audit_entry, sort_keys=True) + "\n")
        status_audit = True
    except Exception:
        status_audit = False

    if as_json:
        print(json.dumps(summary, indent=2, sort_keys=True))

    return Result(True, {"summary": summary, "audit_written": status_audit})


# ---- CLI wiring --------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="madctl", description="MAD-OS syscall CLI")
    p.add_argument("--json", action="store_true", help="JSON output")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("health")

    la = sub.add_parser("list")
    la.add_argument("what", choices=["adapters"])

    d = sub.add_parser("describe")
    d.add_argument("adapter")

    e = sub.add_parser("explain")
    e.add_argument("adapter")
    e.add_argument("--input", required=True)

    r = sub.add_parser("run")
    r.add_argument("adapter")
    r.add_argument("--input", required=True)
    r.add_argument("--scope", default="read-only", choices=["read-only", "operator"])
    r.add_argument("--dry-run", action="store_true")

    # pull repos: archaeology mode
    pull = sub.add_parser("pull")
    pull_sub = pull.add_subparsers(dest="subject", required=True)

    repos = pull_sub.add_parser("repos")
    repos.add_argument("--repo", dest="repos", action="append", default=[], help="Repository URL (repeatable)")
    repos.add_argument("--file", dest="file", help="File with repo URLs, one per line")
    repos.add_argument("--root", dest="root", default=str(Path(os.environ.get("HOME", "~")) / "mad-os-research"), help="Root dir to store repos")
    repos.add_argument("--json", action="store_true", help="JSON output for pull results")

    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env = dict(**{k: v for k, v in os.environ.items()}) if hasattr(os, "environ") else {}

    if args.cmd in ("status", "health"):
        res = cmd_status(env)
    elif args.cmd == "list" and getattr(args, "what", None) == "adapters":
        res = cmd_list_adapters()
    elif args.cmd == "describe":
        res = cmd_describe(args.adapter)
    elif args.cmd == "explain":
        res = cmd_explain(args.adapter, args.input)
    elif args.cmd == "run":
        res = cmd_run(args.adapter, args.input, args.scope, args.dry_run, env)
    elif args.cmd == "pull" and getattr(args, "subject", None) == "repos":
        # collect repos
        repos: List[str] = []
        if getattr(args, "file", None):
            try:
                for line in Path(args.file).read_text().splitlines():
                    line = line.strip()
                    if line:
                        repos.append(line)
            except Exception as e:
                print(f"Error reading file {args.file}: {e}")
                return 2
        repos.extend(getattr(args, "repos", []) or [])
        if not repos:
            print("No repos provided")
            return 2
        res = cmd_pull_repos(repos, Path(args.root), as_json=args.json)
    else:
        return 2

    _print(res.data, getattr(args, "json", False))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
