Phase‑4 Test Plan

Status: Draft (Phase‑4 gating; Hermes review required)

Executive Summary

This test plan directly validates the acceptance criteria in ADR‑009…ADR‑014. It defines unit, integration, and load tests that must pass (or be explicitly acknowledged with mitigations) before Phase‑4 enforcement wiring is merged.

Gating Principle

Every acceptance criterion in the ADR addenda maps to at least one automated test. Phase‑4 is blocked until all critical tests pass and Hermes explicitly signs off.

Test Matrix

1) Signing & Canonical Serialization
- Type: Unit / Integration
- Description: Verify that all signed artifacts (DOs, ROs, audit checkpoints) are serialized using the canonical serializer and validate signatures using Hermes public keys. Cover key rotation scenarios and invalid key cases.
- Expected Outcome: Canonical bytes match golden vectors; signature validation succeeds for valid keys and fails otherwise.
- Automation Hook: `tests/integration/test_signing.py`, `scripts/phase4_signing_test.py`
- Test Data: Keypair fixtures, canonical serialization vectors, rotated-key scenarios

2) Revocation Enforcement & Propagation SLA
- Type: Integration / Load
- Description: Issue a revocation and verify immediate local enforcement; measure propagation latency to remote nodes/observers and assert it meets SLA (e.g., internal <30s, cross-federation <5m).
- Expected Outcome: Revoked DOs denied immediately; propagation latency within SLA for 99th percentile.
- Automation Hook: `tests/integration/test_revocation_propagation.py`, `scripts/phase4_revocation_sla.py`
- Test Data: Two-node topology (authority + observer), revocation events, timing harness

3) Monotonic Counters & Anti‑Replay
- Type: Load / Integration
- Description: Simulate high-concurrency increments, node failover and restart, and validate counter monotonicity and no duplicates/replays.
- Expected Outcome: No counter duplication or regression after failover; replay attempts rejected and audited.
- Automation Hook: `tests/load/test_counters.py`, `scripts/phase4_counter_failover.py`
- Test Data: High-concurrency workloads, failover scripts

4) Tamper Detection on Audit Log
- Type: Integration
- Description: Create audit records, then tamper records (modify/delete/reorder) and run verification tool to detect anomalies.
- Expected Outcome: Verification detects tampering and reports exact discrepancies; integrity verification script passes against untampered logs.
- Automation Hook: `tools/audit_verify.py`, `tests/integration/test_audit_tamper_detection.py`
- Test Data: Sample audit DB snapshot, tampered snapshot

5) Clock Skew & Expiry Enforcement
- Type: Integration
- Description: Inject clock skew into TimeProvider, test issuance and expiry of DOs/ROs, and verify that extreme skews cause deny and alerting.
- Expected Outcome: Expiry and issuance windows respected; extreme skews cause fail-closed behavior and alerts.
- Automation Hook: `tests/integration/test_clock_skew.py`, `scripts/phase4_clock_skew.py`
- Test Data: Delegation tokens with lifetimes, controlled clock injection

6) Metrics & SLA Regression
- Type: Integration / Smoke
- Description: Validate metric emission for revocations, propagation latency, key rotations, audit verification, and counters. Gate PRs on no metric regressions.
- Expected Outcome: Metrics available and within thresholds; regression test fails if metrics deviate from baseline.
- Automation Hook: `tests/integration/test_metrics_sla.py`, metrics smoke tests
- Test Data: Metrics endpoints, expected threshold values

Automation & CI

- Add these tests to CI (prefer staged runs): unit fast tests per-commit; integration tests on PR; load tests on scheduled pipelines or dedicated infra.  
- Provide `scripts/` harnesses for timing-sensitive tests (revocation propagation, counter failover, clock skew) that can run in CI or local lab environments.

Acceptance Criteria for Merge

- All unit tests pass.  
- All integration tests pass in an infra-approved environment (or exceptions documented and accepted by Hermes).  
- Load tests indicate counters and revocation checks meet performance SLOs at expected load.  
- Audit verification tooling reports no integrity issues.

Runbook Notes (short)

- Test infra must allow time control (fake-time injection or container time namespaces) for deterministic skew testing.  
- Revocation propagation tests need at least two nodes (authority + observer) and controllable network latency.

Contact

Tag: @hermes (approval), @qa (test infra)