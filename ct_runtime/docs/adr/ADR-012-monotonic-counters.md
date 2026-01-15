Status: Draft (For Hermes Review)

Decision

Hermes enforces monotonic counters per delegation to prevent replay and reordering.

Context

Nonce-only systems are insufficient under retry and network reordering scenarios.

Consequences
	•	Hermes tracks counters per delegation_id.
	•	Out-of-order or reused counters ⇒ deny + incident.
	•	Counters survive restarts (durable).

Acceptance Criteria
	•	Counter regression always denied.
	•	Counters are monotonic and persisted.
	•	Replay attempts emit security audit events.

Code / Tests
	•	ct_runtime/core/counters.py (new)
	•	guarded_executor.py (counter enforcement)
	•	Tests: replay, out-of-order, restart continuity
