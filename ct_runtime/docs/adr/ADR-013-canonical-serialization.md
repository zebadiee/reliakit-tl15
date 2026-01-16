Status: Draft (For Hermes Review)

Decision

All signed artifacts (DOs, ROs, audit hashes) use a canonical, deterministic serialization.

Context

Non-canonical JSON breaks signature verification and audit integrity.

Consequences
	•	Canonical serialization is mandatory before signing or hashing.
	•	Field order, encoding, and whitespace are fixed.
	•	Any non-canonical input ⇒ deny.

Acceptance Criteria
	•	Identical logical payloads produce identical bytes.
	•	Signature verification fails on non-canonical input.
	•	Golden vectors validate serialization stability.

Code / Tests
	•	ct_runtime/core/serialization.py (new)
	•	Tests: golden vectors, reordering, whitespace variance
