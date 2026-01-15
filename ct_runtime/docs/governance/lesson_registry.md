# Lesson Registry

The `lessons.yaml` registry captures deterministic lessons extracted from failures/recovery events.

Schema:
- id: unique rule id (string)
- source: originating result id or recovery note (string)
- rule: short human-readble rule (string)
- enforced_by: subsystem that should enforce (e.g., `execution_map`) (string)
- confidence: `low|medium|high` (string)
- first_seen: ISO timestamp (string)

Operational notes:
- The `obsidian_sync` script extracts lessons as YAML and appends them to `/srv/ct/lessons.yaml`.
- Lessons are **read-only** for the watcher until a human review converts them into `execution_map` entries.
- Change process: review lessons in Obsidian, update execution_map after approval, then remove or mark lessons as encoded.
