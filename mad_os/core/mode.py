from __future__ import annotations

from enum import Enum
from typing import Mapping


class Mode(str, Enum):
    OBSERVER = "observer"
    OPERATOR = "operator"
    APPRENTICE = "apprentice"
    LOCKED = "locked"


def resolve_mode(env: Mapping[str, str]) -> Mode:
    """Resolve mode from a provided mapping.

    This function is pure and side-effect free. Callers should pass an
    environment-like mapping (e.g., os.environ or a test dict).

    Resolution priority (simple, explicit):
    - If CT_MODE present and matches a Mode member -> return that
    - Else if TAQCO_MODE present and matches a Mode member -> return that
    - Else default to OBSERVER
    """
    if not env:
        return Mode.OBSERVER

    # Normalise keys & values
    def _norm(s: str) -> str:
        return s.strip().lower()

    # CT_MODE has higher priority
    ct = env.get("CT_MODE") or env.get("ct_mode")
    if ct:
        val = _norm(ct)
        for m in Mode:
            if m.value == val or m.name.lower() == val:
                return m
    taq = env.get("TAQCO_MODE") or env.get("taqco_mode")
    if taq:
        val = _norm(taq)
        for m in Mode:
            if m.value == val or m.name.lower() == val:
                return m

    return Mode.OBSERVER
