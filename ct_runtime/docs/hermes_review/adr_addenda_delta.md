Hermes Review Delta: ADR Addenda (ADR-009 → ADR-014)

Executive Summary

This change adds six short, authoritative ADR addenda that close known design gaps required before Phase‑4 enforcement wiring: Key Management & Signing, Time & Clock Skew, Revocation Registry & SLA, Monotonic Counters & HA semantics, Canonical Serialization, and Tamper‑Evident Audit Chain. Each addendum is prescriptive and gates Phase‑4 implementation; acceptance criteria are explicit and testable.

Acceptance Checklist (PR Gating)

- [ ] ADR-009 — Key Management & Signing added to `docs/adr/` and acknowledged by Hermes
  - [ ] All DOs/ROs signed by Hermes keys
  - [ ] Signature verification enforced (fail-closed)
- [ ] ADR-010 — Time & Clock Skew added
  - [ ] TimeProvider abstraction added; no inline wall-clock in enforcement paths
  - [ ] Skew tolerance defined and tested
- [ ] ADR-011 — Revocation Registry & SLA added
  - [ ] Revocation registry defined and auditable
  - [ ] Per-invocation revocation checks and SLA validated
- [ ] ADR-012 — Monotonic Counters added
  - [ ] Persistent monotonic counters per delegation_id
  - [ ] Replay/regression tests in place
- [ ] ADR-013 — Canonical Serialization added
  - [ ] Canonical serializer specified and golden vectors provided
- [ ] ADR-014 — Tamper-Evident Audit Chain added
  - [ ] Audit chain verification tooling available

Phase‑4 Gating Conditions

1. The six ADRs are accepted by Hermes (explicit sign-off).  
2. Implementation plan and API surface for `core/keys.py`, `core/time.py`, `core/revocation.py`, `core/counters.py`, `core/serialization.py`, and audit chaining is submitted and reviewed.  
3. Phase‑4 test plan (unit, integration, load) is drafted and linked in PR.  
4. CI gating added to validate the Phase‑4 acceptance tests before merge.

Next Steps

1. Hermes review & sign-off on the six ADRs.  
2. After sign-off, proceed to Phase‑4 implementation and test plan (staged PRs per module).  
3. Add CI tasks to run Phase‑4 gating tests and infra provisioning for integration/load tests.

Contact

For questions, tag: @hermes (technical authority) and @security (policy & audit).