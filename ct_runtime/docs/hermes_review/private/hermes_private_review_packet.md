Hermes Private Review Packet (Draft — Private Review Only)

Status: DRAFT (Private review — do NOT publish)

Executive Summary

This packet contains the Phase‑3 → Phase‑4 preconditions for Hermes review. It includes the six ADR addenda (ADR‑009…ADR‑014), the Phase‑4 test plan, and the Hermes sign‑off packet. This is for private review only; do not push a branch or open a PR until Hermes provides private approval to proceed to the formal PR step.

Contents

1. ADR Addenda (see `docs/adr/`):
   - ADR‑009 — Key Management & Signing
   - ADR‑010 — Time & Clock Skew
   - ADR‑011 — Revocation Registry & SLA
   - ADR‑012 — Monotonic Counters & HA
   - ADR‑013 — Canonical Serialization
   - ADR‑014 — Tamper‑Evident Audit Chain

2. Phase‑4 Test Plan (see `docs/hermes_review/phase4_test_plan.md`) — outlines unit, integration, and load tests that map directly to the ADR acceptance criteria.

3. Hermes Sign‑off Packet (see `docs/hermes_review/hermes_signoff_packet.md`) — contains the acceptance checklist and the sign‑off template.

Private Review Instructions

- Read the ADRs and Phase‑4 test plan for coverage and acceptance criteria.
- Use the acceptance checklist in the Hermes sign‑off packet to validate readiness.
- If no objections, provide **private approval** (see `private_approval_statement.txt`) which allows the team to open the formal PR. This private approval is *not* a public GitHub approval; it is a governance green light for creating the PR.

PDF generation (optional)

To produce a PDF for Hermes use (run locally):

```
# Install pandoc if needed, then:
pandoc -s hermes_private_review_packet.md -o Hermes_Private_Review_Packet.pdf
```

Security & Handling

- This packet is confidential until Hermes authorizes PR publication.
- Do not distribute or publish these materials outside the Hermes review process.

Contact

For questions, tag: @hermes (review), @security (policy), @infra (test infra).