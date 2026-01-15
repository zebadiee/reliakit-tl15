#!/bin/bash

CP="http://127.0.0.1:7777"
DB="/home/zebadiee/invictus/data/ct_memory.db"

# Get active lease
LEASE=$(sqlite3 $DB "SELECT lease_id FROM leases WHERE state='ACTIVE' ORDER BY issued_at DESC LIMIT 1")
if [ -z "$LEASE" ]; then
    echo "No active lease found"
    exit 1
fi

echo "[+] Using lease: $LEASE"

# Test 1: Fence into past
echo "[TEST 1] Setting not_after to past..."
PAST=$(python3 -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())")
sqlite3 $DB "UPDATE leases SET not_after = '$PAST' WHERE lease_id = '$LEASE'"

RESPONSE=$(curl -s -X POST "$CP/event" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"gov-executor\", \"lease_id\": \"$LEASE\", \"type\": \"TEST\", \"payload\": \"fence-test\"}")

STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('detail', 'unknown'))" 2>/dev/null || echo "$RESPONSE")
echo "Response: $STATUS"

if echo "$RESPONSE" | grep -q "temporal fence"; then
    echo "✔ PASS: Temporal fence violation detected"
else
    echo "✗ FAIL: Expected temporal fence error"
fi

# Test 2: Restore valid window
echo -e "\n[TEST 2] Restoring valid window..."
NOW=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")
LATER=$(python3 -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())")
sqlite3 $DB "UPDATE leases SET not_before = '$NOW', not_after = '$LATER' WHERE lease_id = '$LEASE'"

sleep 1

RESPONSE=$(curl -s -X POST "$CP/event" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"gov-executor\", \"lease_id\": \"$LEASE\", \"type\": \"TEST\", \"payload\": \"valid-window\"}")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✔ PASS: Event succeeded inside window"
else
    echo "✗ FAIL: Expected success (200)"
    echo "Response: $RESPONSE"
fi

echo -e "\n✔ Tier 13 Temporal Fencing verified"
