Title: chore(mad_os): add skeleton package + import-safety and mode tests

Summary:
- Add a minimal, side-effect-free `mad_os/` package (skeleton only) under repository root.
- Implemented `mad_os/core/mode.py` with a pure `Mode` enum and `resolve_mode(env)` helper.
- Added `mad_os/capabilities.py` (pure dataclasses + explicit registry API; no registration on import).
- Added tests to verify import-safety and Mode contract (`tests/test_mad_os_imports.py`, `tests/test_mad_os_mode_contract.py`, `tests/test_mad_os_capabilities.py`).
- Added a lightweight GitHub Actions workflow to run tests on PRs that touch `mad_os/**` or `tests/**`.

Why:
- Establishes the MAD-OS namespace as a safe, importable boundary for future migration.
- Enforces the rule that importing `mad_os` must never cause side-effects (writes, DB, asserts, network, or threads).

What I ran/validated locally:
- Manual import checks with PYTHONPATH set to the repo root (no side effects observed).
- Mode and capabilities checks (pure, deterministic).

Suggested next steps:
- Create thin re-exports for safe modules under `mad_os/` and add import tests for each.
- Refactor the top 3 side-effecting modules to be import-safe (prepare for future migration).
- Add a PR template and link to MAD-OS blueprint doc in Obsidian when structure stabilizes.

Link: create a PR on GitHub: https://github.com/zebadiee/reliakit-tl15/pull/new/mad-os/skeleton
