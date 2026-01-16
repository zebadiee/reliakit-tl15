Hermes Sign-off Packet (Phase‑4 Preconditions)

Status: Draft (Hermes review required)

Summary

This packet summarizes the ADR addenda (ADR‑009…ADR‑014), the Phase‑4 test plan, and the exact acceptance criteria required for Hermes sign‑off prior to enforcement wiring.

Core Decisions (short)
- Hermes is sole authority for keys and signatures (ADR‑009).  
- Time is canonical and bounded by explicit skew (ADR‑010).  
- Revocation is authoritative and SLA-bound (ADR‑011).  
- Counters are per-delegation and monotonic with HA durability (ADR‑012).  
- A canonical serializer is required for signing/hashing (ADR‑013).  
- Audits are append-only and chained for tamper detection (ADR‑014).

Hermes Acceptance Checklist (PR sign‑off)
- [ ] ADR‑009 … ADR‑014 are accepted by Hermes.  
- [ ] Phase‑4 Test Plan (`docs/hermes_review/phase4_test_plan.md`) is accepted (or test infra exceptions documented).  
- [ ] Implementation plan(s) submitted and reviewed for each module (`core/keys.py`, `core/time.py`, `core/revocation.py`, `core/counters.py`, `core/serialization.py`, audit chaining).  
- [ ] DB schema/migration plan for revocation, counters, and audit chain included and reviewed.  
- [ ] CI plan for gated tests (unit, integration, load) and required infra is accepted.

Hermes Sign-off Template (copy-paste)

> Reviewed ADR‑009..ADR‑014; acceptance criteria satisfied. Hermes signs off — proceed to Phase‑4 enforcement wiring.

Post-Signoff Requirements

- Merge small, focused implementation PRs with accompanying tests (per the Implementation PR Checklist).  
- Add runtime observability dashboards for revocation, counters, and audit integrity.  
- Schedule an enforcement rollout window with security monitoring enabled.

Contact

Tag: @hermes (approval), @security (incident handling), @infra (test infra)