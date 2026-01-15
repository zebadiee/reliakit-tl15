Phase‑4 Start Trigger (Authoritative)

Status: Draft (ready-to-commit)

Decision

Phase‑4 (Enforcement Wiring) SHALL begin only when a public, verifiable Hermes approval artifact exists for PR `adr/addenda/phase4-preconditions`.

Operational trigger (machine-checkable)

- PR exists with branch `adr/addenda/phase4-preconditions` AND
- One of the following is true:
  - `review.state == APPROVED` by Hermes (GitHub approve review), OR
  - The PR is merged by Hermes.

When the trigger is satisfied:
1. Mark ADR‑009..ADR‑014 as LOCKED and authoritative.
2. Enable the Phase‑4 task graph and allow implementation PRs to proceed.
3. Unfreeze feature‑flagged enforcement wiring according to rollout plan.
4. Require Phase‑4 test plan gating on all enforcement PRs.

Enforcement and embedding

This trigger SHOULD be embedded in:
- `docs/governance/phase_transitions.md` (this file)
- CI policy checks (example in `docs/ci/phase4_approval_gate_example.yml`)
- PR templates (see `.github/PULL_REQUEST_TEMPLATE/phase4_pr_template.md`)

Notes

- Private or informal Hermes approvals (DMs, verbal) are insufficient. Only a public Approve review by Hermes or a Hermes merge qualifies.
- This rule is intentionally strict to preserve governance audibility and prevent accidental scope creep.