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

## Design: Core Invariants and Procedures

### Ownership model
- Only agents with an allowed role (by default: `executor`) or those explicitly listed in a delegation policy may delegate authority.
- Delegation requires **signed consent** from the parent agent. Consent is a deterministic message signed by the parent's registered key and stored in the `events` table and appended to Obsidian as a governance record.
- Consent message format (deterministic for signature and audit):
  - `DELEGATE|<parent_lease_id>|<child_agent_id>|<child_not_before>|<child_not_after>|<nonce>`
- Parent must explicitly sign consent and the control plane will verify the signature using `agent_keys` before accepting a delegated child.

### Delegation invariants
- **Temporal containment:** child `not_before` >= parent `not_before`; child `not_after` <= parent `not_after`.
- **Depth limit:** `delegation_depth` is an integer; child depth = parent depth + 1; system enforces `child_depth <= MAX_DELEGATION_DEPTH` (default 2).
- **Scope & capabilities:** child inherits a subset of parent's capabilities; explicit policy may restrict which capability subsets are delegable.
- **No ownership transfer:** parent remains the canonical owner; delegation grants bounded authority only for the child lease instance.

### Consent & Authorization semantics
- Consent must be fresh (nonce + short window) and signature verified using `agent_keys`.
- The system stores the consent as an auditable event and appends a governance note in Obsidian referencing both parent and child leases.
- Delegation requests without valid consent are rejected with a clear, auditable error (e.g., `delegation requires parent consent`).

### Revocation & Cascade
- The `revoke_lease_tree(lease_id)` function must revoke the specified lease and recursively revoke all descendants in a transactional manner.
- Revocation must emit a governance event (and Obsidian entry) containing `root_lease`, list/count of children revoked, and revoker identity.
- On revocation, ensure resource cleanup: remove `lease_consumers`, update state to `REVOKED`, and insert events for auditing.

### Audit & Governance
- All delegation-related actions (attempts, consents, grants, revocations) are recorded in:
  - `events` table (deterministic payloads)
  - `03-Governance-Log.md` (append-only canonical notes)
- Governance entries must include timestamps, actor IDs, lease IDs, and rationale.

### Tests & Validation (Acceptance)
- Unit tests:
  - valid delegation with signed parent consent succeeds
  - child window outside parent rejected (not_before < parent.not_before or not_after > parent.not_after)
  - delegation depth exceed rejected
  - missing/signature mismatch rejected
- Integration tests:
  - cascade revoke deletes children and logs events
  - governance log receives entries for consents and revocations
- Security tests:
  - attempt to forge consent fails signature verification
  - race conditions in revoke are robust (replay and idempotency checks)

### Rollout Plan
1. Implement feature flag `CT_ENABLE_DELEGATION` default `0`.
2. Merge design & tests while guard remains active.
3. Enable in a test environment + smoke tests.
4. Canary enable with monitoring and quick rollback plan.

---

## Activation Checklist (acceptance criteria)
- [x] Design reviewed internally
- [ ] Design approved by governance (admin signatures)
- [ ] Automated tests for delegation invariants implemented and passing
- [ ] Audit of Obsidian entries & test artifacts
- [ ] Rollout plan and feature flag ready for controlled enablement

---

## Change Log
- 2026-01-09T22:13:34Z — Tier 14 sealed (guard added in `ct_server.py`).
- 2026-01-09T22:32:39Z — System snapshot created and state documented (v0.13-sealed).
- 2026-01-09T22:18:00Z — Initial HADES stub created.

---

## Technical Appendix (design reference)

### Data model & event payloads (design-only)
- Consent record (persisted as event):
  - table: `delegation_consents`
  - columns: `consent_id`, `parent_lease_id`, `child_agent_id`, `child_not_before`, `child_not_after`, `nonce`, `signed_by`, `signature`, `issued_at`
  - event payload example:
    ```json
    {
      "type": "DELEGATION_CONSENT",
      "parent_lease_id": "<uuid>",
      "child_agent_id": "bob",
      "child_not_before": "...",
      "child_not_after": "...",
      "nonce": "...",
      "signed_by": "alice",
      "signature": "<b64sig>",
      "issued_at": "..."
    }
    ```

### Deterministic signing & verification
- Use existing `agent_keys` table for signature verification (Ed25519). Signatures must be verified before granting delegated leases.
- Message binding MUST include parent lease id and full child execution window to prevent replay or substitution.

### API (design-only) flow
1. Parent agent produces a consent message and signs it off-chain (or via `admin` endpoint), storing consent as event.
2. Child agent submits `/lease/request` with `parent_lease_id` plus `consent` payload (nonce + signature).
3. Server verifies:
   - parent lease active
   - parent owns the lease
   - consent signature valid and nonce unused
   - time window subset check
   - delegation depth within limits
   - requested capabilities subset of parent's capabilities
4. If all checks pass and `CT_ENABLE_DELEGATION=1`, grant child lease and record event + governance note.

### Sign-off template (for governance approval)
- **Design**: HADES Tier 14 delegation model
- **Reviewed by**: ____________________
- **Approved by**: ____________________ (admin id + signature)
- **Date**: ____________________
- **Conditions**: tests passing; roll-back plan ready; limited canary enablement

---

## Review & Sign-off
**Commit:** `6ce6fda`  
**Tag:** `v0.13-sealed`  
**Status:** SUBMITTED FOR REVIEW — design-only (no execution changes)

**Required approvals:**
- Owner (root-admin)
- Security Lead (security-admin)
- Governance Admin (admin-gov-v2)

**Activation conditions (must be true before any implementation enablement):**
- All acceptance tests implemented and passing (unit/integration/security).  
- Governance approvals recorded in this document (signatures or explicit approvals appended).  
- Feature flag `CT_ENABLE_DELEGATION` implemented and defaulted to `0`.  
- Rollback and canary plan documented and tested.  
- External audit of consent signing process completed.

**Review notes:**
- This document is submitted for formal sign-off and should be reviewed by the listed approvers. No code changes will be enabled until an explicit activation record is appended here.

*End of file.*
