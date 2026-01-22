Title: feat(boot): add CT boot-observer mode (snag sweep, audit, READY contract)

Summary
- Introduces `ct_runtime.boot_observer` and a systemd unit template `ops/ct-boot-observer.service`.
- Adds a canonical READY contract written to `/run/dam-os/READY` (JSON payload, perms enforced).
- Adds append-only JSONL audit entries to `~/.mad_os/AUDIT.log` (sha256 envelope) for `boot.sweep` events.
- Adds unit tests `tests/test_boot_observer.py` and an ops helper template for `madctl status` visibility.

Why
- Ensures boot is observable, deterministic, and governance-ready.
- Promotes CT from a runtime guardian to a boot sentinel that validates invariants before mutating phases run.

What it does (how)
- `ct_runtime.boot_observer` (import-safe module) implements `main(dry_run=False)`:
  - Executes a snag sweep script (`/usr/local/bin/system_snag_sweep.sh`) in read-only mode.
  - Evaluates a small set of invariants (network, docker, disk writable, authority lock present).
  - Produces a verdict: `READY` or `HALT` (future: `DEGRADED`).
  - Appends a JSONL audit entry with `action=boot.sweep`, `status`, `checks`, `sweep_ok` and `ts`, and writes an SHA256 envelope line.
  - Writes the READY JSON file to `/run/dam-os/READY` (payload with `status`, `ts`, `verifier`, `note`) with best-effort permissions (0640).
- Systemd unit template `ops/ct-boot-observer.service` provided (disabled by default). Core runtimes should use `After=ct-boot-observer.service` and `Requires=` to gate starting on success.

Safety guarantees
- Import-safe: module import does nothing. All behavior happens when `main()` is invoked or via `ct --mode boot-observer`.
- Non-mutation: snag sweep and probe operations are read-only; only verdict+audit are written.
- Append-only audit: audit entries are never overwritten; they are JSONL with a SHA envelope per entry.

Tests & Manual verification
- Unit tests: `tests/test_boot_observer.py`
  - `test_boot_observer_dry_run_records_audit`: dry-run must append audit and not write READY.
  - `test_boot_observer_halt_on_missing_invariant`: simulates failed invariant and asserts HALT audit + SystemExit.
- Manual smoke checks performed locally (no systemd required): used a temporary snag script and verified audit entries and HALT/READY behavior.

Manual verification steps (ops)
1. Copy `system_snag_sweep.sh` to `/usr/local/bin/system_snag_sweep.sh` and make executable.
2. Run: `ct --mode boot-observer --dry-run` (expect audit entry, no READY file).
3. Run: `ct --mode boot-observer` (expect `/run/dam-os/READY` with `READY` or `HALT`).
4. Check last audit: `tail -n 5 ~/.mad_os/AUDIT.log`.

Enablement checklist (review & preconditions)
- [ ] Provide or validate `system_snag_sweep.sh` on hosts.
- [ ] Decide exact invariants & adjust `invariants()` as required.
- [ ] Stage test deployment on a non-production node.
- [ ] Review systemd unit and decide if `Before=`/`After=` ordering is correct for your environment.
- [ ] Ensure `/run` tmpfs is available and PID 1 boots early enough.

Enablement command (ops only)
- `sudo cp ops/ct-boot-observer.service /etc/systemd/system/`
- `sudo systemctl daemon-reload`
- `sudo systemctl start ct-boot-observer.service`
- If behavior is as expected: `sudo systemctl enable ct-boot-observer.service`

Rollback / disable
- To disable the observer (no runtime changes): `sudo systemctl disable --now ct-boot-observer.service` and remove the READY file if present: `sudo rm -f /run/dam-os/READY`.

Follow-ups / roadmap
- Add `madctl status` insight (already surfaces last audit and READY in this change).
- Port snag probes into CT-native probes (Python) for richer asserts and better test coverage.
- Consider signing audit entries (GPG/PKI) in a later enhancement.

Notes
- This is intentionally conservative: it does not enable systemd by default – enforcement must be opted-in after review.

PR draft link (open in browser to finish): https://github.com/zebadiee/reliakit-tl15/pull/new/mad-os/boot-observer
