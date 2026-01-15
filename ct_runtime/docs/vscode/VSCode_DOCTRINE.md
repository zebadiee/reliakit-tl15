# CT VS Code Doctrine

**Core shift:** VS Code is the agent console, planning surface, coordination bus, and observability layer.

## One workspace
Create a single workspace on Hermes and open it only there. See `/srv/ct/workspace/CT.code-workspace`.

## Terminals = Agents
Rename terminals to reflect responsibilities (WATCHER, QUEUE, RESULTS, LOGS, EXPERIMENT), and pin monitoring commands.

## Copilot as subordinate
Limit Copilot to drafting intents, extending watcher logic, writing recovery docs, and generating tests. Never allow it to decide execution or invent authority.

## Agent collaboration
Split panes to show `/srv/ct/queue`, `/srv/ct/results`, and logs. Agents coordinate through files and durable state only.

## Failure workflow
Keep a snippet `CT_FAILURE_TEST` to intentionally break things and observe recovery, logging, and Obsidian notes.
