Phase‑4 Preconditions PR Template

Status: Draft (use for PRs that implement Phase‑4 preconditions)

Summary

- This PR implements Phase‑4 preconditions (documentation, test plans, gating artifacts). No enforcement code should be included in this PR.

Governance invariant

> No enforcement code may be written, merged, or enabled unless Hermes has publicly approved the governing ADRs.

Requirements (before merge)

- [ ] This PR is docs-only (no code or schema changes).  
- [ ] PR targets `main` and originates from `adr/addenda/phase4-preconditions`.  
- [ ] Hermes is assigned as reviewer.  
- [ ] Hermes must explicitly Approve this PR or merge it (Approve review by Hermes or Hermes-merge).  

Acceptance Checklist (Hermes)

- [ ] ADR-009 — Key Management & Signing
- [ ] ADR-010 — Time & Clock Skew
- [ ] ADR-011 — Revocation Registry & SLA
- [ ] ADR-012 — Monotonic Counters
- [ ] ADR-013 — Canonical Serialization
- [ ] ADR-014 — Tamper‑Evident Audit Chain
- [ ] Phase‑4 test plan accepted
- [ ] Implementation checklist accepted

Notes

- Private approvals are useful for preparing the PR, but do NOT replace the public Approve review requirement.
- For the authoritative Phase‑4 trigger and an example CI gate, see `docs/governance/phase_transitions.md` and `docs/ci/phase4_approval_gate_example.yml`.