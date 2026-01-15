Status: Draft (For Hermes Review)

Decision

Hermes defines canonical time; all policy evaluation uses a single abstracted clock with bounded skew tolerance.

Context

TTL enforcement, cooldowns, and revocation require deterministic time semantics across nodes.

Consequences
	•	All time access routes through core/time.py.
	•	Delegates may not override time sources.
	•	Excessive skew results in deny, not correction.

Acceptance Criteria
	•	No direct datetime.utcnow() usage in enforcement paths.
	•	Skew tolerance is explicit and bounded.
	•	Time uncertainty ⇒ deny execution.

Code / Tests
	•	ct_runtime/core/time.py (new)
	•	Replace inline datetime usage
	•	Tests: skew tolerance, expired DO, future-issued DO
