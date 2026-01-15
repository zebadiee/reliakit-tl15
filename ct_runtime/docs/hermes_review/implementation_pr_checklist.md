Phase‑4 Implementation PR Checklist

Status: Draft (Implementation guidance & PR gating)

Purpose

Break Phase‑4 into small, reviewable PRs with clear acceptance tests and minimal blast radius. Use this checklist as a template for each implementation PR.

Per‑PR Template (required items)
- PR scope description (one sentence).  
- ADR reference(s) (which ADRs this PR implements).  
- Code changes limited to a single concern (e.g., `core/time.py` + tests only).  
- Unit tests added and passing.  
- Integration tests added or a ticket pointing to test infra (if test requires multi-node infra).  
- DB migration included (if persistent state added) and migration test included.  
- Observability: Metrics added and documented.  
- Security: Signature/key usage reviewed and threat model OK.  
- Ops: Runbook or rollback notes included (key rotation, audit verify steps).

Suggested PR grouping & priorities
1) `core/time.py` + replace inline datetime usage (low risk).  
2) `core/serialization.py` + golden vector unit tests (blocks signing and audits).  
3) Audit chain changes in `core/audit.py` and `tools/audit_verify.py` + integration tamper tests.  
4) `core/keys.py` (KMS/HSM abstraction + software fallback) + signing/verification tests.  
5) `core/revocation.py` (registry + propagation hooks) + per-invocation tests + metrics.  
6) `core/counters.py` (HA monotonic counters) + failover tests and load testing.

CI Requirements
- Unit tests run on every PR.  
- Integration tests (time-sensitive, multi-node) run on merge candidate or scheduled pipeline with dedicated infra.  
- Load tests for counters and revocation propagation run in staging prior to wide rollout.

Merge Criteria
- All required tests pass and performance SLOs met or an explicit mitigation is approved.  
- DB migrations reviewed and rollback tested.  
- Observability dashboards present basic SLOs and alerts.

Rollout Guidance
- Feature-flag enforcement wiring to allow staged rollout (disable by default).  
- Canary enforcement on a small subset of traffic, monitor audit + metrics for 24–72 hours.  
- Full rollout only after successful canary and no critical incidents.

Contact

Tag: @hermes (design), @security (policy), @infra (test infra)