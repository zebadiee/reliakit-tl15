# Execution Map

The `execution_map` defines authoritative actions and the rules that govern them.

Schema (execution_map.yaml):
- description: short text
- allow: optional list of agent names (or `*`) that are permitted to run the action. If present, this list **overrides** agent-level `allow` lists.
- escalation_required: boolean; if true, the action requires explicit approval (`approved_by` in the job) before execution.
- reversible: boolean describing whether the action is reversible.

Operational notes:
- The watcher enforces this map at runtime and logs every decision as `ACTION_CHECK`.
- Changes to `/srv/ct/execution_map.yaml` take effect on the next watcher evaluation.
- New actions should be added only after human review and an Obsidian note describing intent and rollback.
