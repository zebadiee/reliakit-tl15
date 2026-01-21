"""MAD-OS package root — thin re-exports and public API.

Importing anything under `mad_os` must not produce side effects (no files, DB, threads, network, or asserts at import time).
"""

__version__ = "0.1.0"

# Re-export core safe symbols
from .core.mode import Mode, resolve_mode

__all__ = ["Mode", "resolve_mode", "__version__"]
