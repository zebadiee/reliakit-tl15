Status: Draft (For Hermes Review)

Decision

Revocation is immediate, authoritative, and SLA-bound; failure to confirm revocation state MUST deny execution.

Context

Phase 3 requires revocation to override all other permissions deterministically.

Consequences
	•	Hermes maintains the revocation registry.
	•	Delegates must check revocation state before every invocation.
	•	Registry unavailability ⇒ fail-closed.

Acceptance Criteria
	•	Revoked DOs cannot execute within SLA bounds.
	•	Revocation checks occur per invocation.
	•	Revocation events are auditable and signed.

Code / Tests
	•	ct_runtime/core/revocation.py (new)
	•	guarded_executor.py (revocation check)
	•	Tests: revoked DO, registry unreachable, SLA timing
