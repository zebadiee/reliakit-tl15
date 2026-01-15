PROMPT: CONTINUE EXECUTION (Short System Version)

When the following conditions are met, proceed to Phase‑4 enforcement wiring:

- A Pull Request exists from branch `adr/addenda/phase4-preconditions` containing:
  - `docs/adr/ADR-009` → `ADR-014` (accepted addenda),
  - `docs/hermes_review/phase4_test_plan.md`,
  - `docs/hermes_review/hermes_signoff_packet.md`,
  - `docs/hermes_review/implementation_pr_checklist.md`.
- Hermes has explicitly approved the PR (approval comment or merge approval).

On Hermes approval:
- Treat ADR-009..ADR-014 as locked and authoritative.
- Finalize Phase‑4 enforcement wiring plan and generate implementation PR(s).
- Map code-level checklist directly to the approved ADRs and prepare minimal, auditable changes.

If Hermes requests changes:
- Pause execution and apply only the requested modifications to ADRs or review materials.
- Re-submit for Hermes approval and remain idle until approval is confirmed.

Do not introduce new scope, policy, or governance changes beyond the approved ADRs.