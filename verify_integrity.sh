#!/bin/bash

# verify_integrity.sh
# Verifies the integrity of key ReliaKit files by comparing their content
# with expected, known-good versions.

# Function to get SHA256 checksum of a file
get_checksum() {
    shasum -a 256 "$1" | awk '{print $1}'
}

# --- Expected Content Hashes ---
# THESE HASHES ARE GENERATED FROM THE *EXACT* CONTENT PROVIDED IN THE MEGA PROMPT.
# If you make any manual changes (even whitespace), the hash will change.

# Expected hash for reliakit/memory_db.py
EXPECTED_MEMORY_DB_HASH="17a6be2f0d4fcc4e70c390c4565325896b3daba7729271f8f2858fbc22223c63"

# Expected hash for memory_seeder.py
EXPECTED_MEMORY_SEEDER_HASH="00d83794fc3e1a45cbfd40b4bd96b14ee5b0fb65759864168c3af73c12b8f2fa"

# --- File Paths ---
MEMORY_DB_FILE="reliakit/memory_db.py"
MEMORY_SEEDER_FILE="memory_seeder.py"

echo "🔍 Verifying file integrity..."

# Verify memory_db.py
if [ -f "$MEMORY_DB_FILE" ]; then
    CURRENT_HASH=$(get_checksum "$MEMORY_DB_FILE")
    if [ "$CURRENT_HASH" == "$EXPECTED_MEMORY_DB_HASH" ]; then
        echo "✅ $MEMORY_DB_FILE is correct"
    else:
        echo "❌ $MEMORY_DB_FILE does NOT match expected version! Current hash: $CURRENT_HASH"
        echo "   Expected hash: $EXPECTED_MEMORY_DB_HASH"
        echo "   Please ensure the file content is exactly as provided in the Canvas."
    fi
else
    echo "❌ $MEMORY_DB_FILE not found!"
fi

# Verify memory_seeder.py
if [ -f "$MEMORY_SEEDER_FILE" ]; then
    CURRENT_HASH=$(get_checksum "$MEMORY_SEEDER_FILE")
    if [ "$CURRENT_HASH" == "$EXPECTED_MEMORY_SEEDER_HASH" ]; then
        echo "✅ $MEMORY_SEEDER_FILE is correct"
    else:
        echo "❌ $MEMORY_SEEDER_FILE does NOT match expected version! Current hash: $CURRENT_HASH"
        echo "   Expected hash: $EXPECTED_MEMORY_SEEDER_HASH"
        echo "   Please ensure the file content is exactly as provided in the Canvas."
    fi
else
    echo "❌ $MEMORY_SEEDER_FILE not found!"
fi

echo "Verification complete."
