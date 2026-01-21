"""Lightweight capability declarations for kernels.

These are pure dataclasses and in-memory registries only; importing this
module must not register or mutate global state on import.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class Capability:
    name: str
    explain: bool = False
    enforce: bool = False
    write_ledger: bool = False
    requires_ai: bool = False
    meta: Dict[str, Any] = None


# Internal registry (only modified when register_capability is called)
_registry: List[Capability] = []


def register_capability(cap: Capability) -> None:
    """Register a capability (explicit call; no side effect on import)."""
    _registry.append(cap)


def registry() -> List[Capability]:
    """Return a snapshot of registered capabilities."""
    return list(_registry)
