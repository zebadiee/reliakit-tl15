# CT Recovery Contract

## Principles
- Failure is non-destructive
- Last-known-good state is authoritative
- Recovery is automatic, logged, and auditable

## Mechanism
- Pre-execution snapshot to `/srv/ct/state`
- On failure:
  - execution halts
  - system reverts to last-known-good
  - result is written
  - recovery is logged

## Learning
Every failure produces:
- a result artifact
- a log entry
- an Obsidian recovery note

No retries without human intent.
