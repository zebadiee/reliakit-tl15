Status: Draft (For Hermes Review)

Decision

The audit log is append-only and cryptographically chained; tampering must be detectable.

Context

Hermes audit records are the system of record for governance and incident response.

Consequences
	•	Each audit entry hashes the previous entry.
	•	Any break in the chain is a security incident.
	•	Verification tooling is mandatory.

Acceptance Criteria
	•	Audit chain verification detects modification, deletion, or reordering.
	•	Hermes is the only writer of authoritative audit entries.
	•	Verification can be run offline.

Code / Tests
	•	Extend audit.py (hash chaining)
	•	tools/audit_verify.py (new)
	•	Tests: tamper detection, truncation, reorder
