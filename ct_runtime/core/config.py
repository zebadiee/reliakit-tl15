# ct_runtime/core/config.py
# =========================================================
# Sealed Governance Configuration
# =========================================================
import os

# Runtime node identity (must be set per node; Hermes must be HERMES)
NODE_ID = os.environ.get("CT_NODE_ID", "UNKNOWN")

# Sealed authority: must NOT be overridable by environment at runtime
SEALED_AUTHORITY_NODE = "HERMES"
