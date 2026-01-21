"""MAD-OS CLI package (import-safe).

This package contains CLI entrypoints. Importing this module must not
cause side-effects; all operations occur when commands are invoked.
"""
__all__ = ["madctl"]
