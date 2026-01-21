"""MAD-OS core package (side-effect free).

This package contains the Mode contract and other small, pure utilities that are safe to import in CLIs, notebooks, tests, and UIs.
"""

from .mode import Mode, resolve_mode

__all__ = ["Mode", "resolve_mode"]
