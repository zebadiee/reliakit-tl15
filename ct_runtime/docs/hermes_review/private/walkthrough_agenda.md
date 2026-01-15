Hermes Private Review — Walkthrough Agenda (15–30 minutes)

Status: DRAFT (Private review only)

Proposed Agenda (15–30 min)

1. Opening (1 min)
   - Purpose and expected outcome (private approval to open PR)

2. Context & invariants (3–5 min)
   - Hermes as single authority (ADR‑001 summary)
   - Scope grammar & deny-by-default (link to ADRs)

3. What ADR‑009..ADR‑014 lock (8–10 min)
   - For each ADR: Decision (one line), key acceptance criteria, and system impact
     - Key Management & Signing (ADR‑009)
     - Time & Clock Skew (ADR‑010)
     - Revocation SLA & Registry (ADR‑011)
     - Monotonic Counters & HA (ADR‑012)
     - Canonical Serialization (ADR‑013)
     - Tamper‑Evident Audit Chain (ADR‑014)

4. Phase‑4 Test Plan & gating (3–5 min)
   - Highlight critical tests and SLOs (revocation propagation latencies, counter load) and handoff to infra for integration runs

5. Questions & Confirms (3–5 min)
   - Any requested wording changes or conditions for approval
   - If accepted: confirm private approval statement and next steps to open PR

6. Next steps & close (1 min)
   - Expected timeline for PR creation and public review

Notes

- Keep discussion focused on acceptance criteria and measurable tests.  
- If Hermes requests edits, we will apply only requested modifications and return for re-check.