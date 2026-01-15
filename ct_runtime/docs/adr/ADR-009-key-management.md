Status: Draft (For Hermes Review)

Decision

Hermes is the sole key authority; all Delegation Objects (DOs) and Revocation Objects (ROs) MUST be signed by Hermes-managed keys.

Context

Phase 3 design requires unforgeable delegation, verifiable revocation, and deterministic enforcement. Key ownership and rotation must not dilute authority.

Consequences
	•	No delegate may generate or rotate authority keys.
	•	Signature verification is mandatory on every guarded execution.
	•	Key rotation is Hermes-only and backward-verifiable for active DOs.

Acceptance Criteria
	•	All DOs/ROs include a Hermes signature.
	•	Verification failure ⇒ deny (fail-closed).
	•	Key rotation does not invalidate unexpired DOs.
	•	Public verification material is read-only to delegates.

Code / Tests
	•	ct_runtime/core/keys.py (new)
	•	guarded_executor.py (verify signatures)
	•	Tests: signature verify, invalid key, rotation continuity
