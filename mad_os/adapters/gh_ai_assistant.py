"""Adapter placeholder for the `gh-ai-assistant` repo (Engine / Kernel).

This module is intentionally side-effect free and only declares capabilities
and a small read-only interface. It must not import the engine modules at
import time to avoid side effects (DB writes, cache updates, threads).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


CAPABILITIES = {
    "explain": True,
    "enforce": False,
    "write_ledger": False,
    "requires_ai": True,
}


@dataclass
class AdapterInfo:
    name: str = "gh-ai-assistant"
    capabilities: Dict[str, Any] = None


def describe() -> AdapterInfo:
    return AdapterInfo(name="gh-ai-assistant", capabilities=CAPABILITIES)


def inputs_schema() -> Dict[str, Any]:
    return {"type": "object", "properties": {"prompt": {"type": "string"}}}


def explain(inputs: Dict[str, Any]) -> Dict[str, Any]:
    raise NotImplementedError("Adapter explain() must be implemented by a runtime binding")


def model_stats() -> Dict[str, Any]:
    """Return read-only model stats (placeholder)."""
    raise NotImplementedError("Adapter model_stats() must be implemented by a runtime binding")
