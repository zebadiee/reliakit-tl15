# CT API CONTRACT — v1 (LOCKED)

Authoritative Node: HERMES

## Registration
POST /node/register
- Used by executors only
- Required fields: agent_id, role=executor, capabilities

## Heartbeat
POST /agent/heartbeat
- executor only
- updates last_seen, status

## Work Polling
GET /task/next
- executor only
- 204 = no work (NO BODY)

## Forbidden (must 404 forever)
- /agent/register
- /agent/hello
- any legacy worker routes

This contract is immutable without a version bump.
