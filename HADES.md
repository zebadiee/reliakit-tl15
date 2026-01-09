# HADES — Tier 14 Design & Seal

**Created:** 2026-01-09T22:18:00Z
**Owner:** root-admin
**Status:** SEALED — delegation disabled (see `TIER14_SEAL.md` and governance log)

## Purpose
This document is the authoritative design & activation record for **Tier 14 — Lease Delegation (Bounded Child Authority)**. It contains activation criteria, design rationale, invariant definitions, and a test checklist to validate safe enabling.

---

## Sections
- **Summary** — short description and security goals
- **Activation Criteria** — what must be true before enabling (policy, audits, tests)
- **Ownership Model** — how ownership and authority transfers are validated
- **Delegation Invariants** — depth limits, temporal containment, signature/consent rules
- **Revocation & Cascade** — how revocation propagates and audit trails
- **Audit & Governance** — Obsidian entries, logs, and external verification
- **Tests & Validation** — acceptance tests to run before enabling
- **Changelog** — record of changes and approvals

---

## Quick Notes
- Current repo state: code contains delegation scaffold in `ct_server.py` but execution path is hard-guarded to reject `parent_lease_id` requests.
- Governance: see `~/Obsidian/CT-Governance/03-Governance-Log.md` for entries including `Tier 14 Sealed` and `Delegation Attempt Rejected`.

---

## Design Stub: Preliminary Invariants
1. Delegation requires explicit signed consent by parent agent (auditably stored).
2. Child lease window must be a subset of parent (`not_before >= parent.not_before`, `not_after <= parent.not_after`).
3. Delegation depth capped (e.g., MAX_DELEGATION_DEPTH = 2).
4. Revocation cascades to all descendants atomically (via `revoke_lease_tree`).
5. All delegation actions must be recorded in Obsidian and events table.

---

## Activation Checklist (acceptance criteria)
- [ ] Design reviewed and approved by governance (admin signatures)
- [ ] Automated tests for delegation invariants pass
- [ ] Audit of Obsidian entries & test artifacts
- [ ] Rollout plan and feature flag for controlled enablement

---

## Change Log
- 2026-01-09T22:13:34Z — Tier 14 sealed (guard added in `ct_server.py`).


*End of file.*
