"""Adapter placeholder for the `ai-cli-sphere` repo (Shell).

This module is intentionally side-effect free. It ONLY declares capability
metadata and a pure interface that MAD-OS can call in OBSERVER mode.

Do NOT import runtime modules from `ai-cli-sphere` at import time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional


CAPABILITIES = {
    "explain": True,
    "enforce": False,
    "write_ledger": False,
    "requires_ai": True,
}


@dataclass
class AdapterInfo:
    name: str = "ai-cli-sphere"
    capabilities: Dict[str, Any] = None


def describe() -> AdapterInfo:
    """Return static descriptor for this adapter (no side effects)."""
    return AdapterInfo(name="ai-cli-sphere", capabilities=CAPABILITIES)


def inputs_schema() -> Dict[str, Any]:
    """Describe expected input shapes for explain/run operations."""
    return {"type": "object", "properties": {}}


def explain(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Explain inputs in read-only mode. Implementations must be deferred to runtime."""
    raise NotImplementedError("Adapter explain() must be implemented by a runtime binding")


def run(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Run the adapter; by default this should be disabled in OBSERVER mode."""
    raise NotImplementedError("Adapter run() is intentionally unimplemented in the placeholder")
