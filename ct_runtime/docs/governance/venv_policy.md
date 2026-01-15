CT Python Virtualenv Policy

Status: Draft (Hermes governance)

Policy

- All Python code that touches CT runtime, governance, unattended automation, or Obsidian vaults MUST run inside one of the canonical CT venvs under `~/ct-venvs/`.
- Canonical venvs (on Hermes):
  - `core` — runtime and shared libraries
  - `agents` — agent processes
  - `tooling` — CLI/tools
  - `experiments` — experimental work
- Every Python script MUST include a header specifying the venv: `# CT_VENV: core` (or agents/tooling/experiments as appropriate).
- Use the provided `~/bin/ct_run` wrapper to execute scripts: `ct_run core path/to/script.py`.
- CI jobs must source the appropriate venv via `ct_run` or by activating `~/ct-venvs/<name>/bin/activate`.

Rationale

- Enforces reproducible environments and isolation.
- Prevents accidental global package installs and drift.
- Ensures governance-sensitive actions run in a known, auditable environment.

Enforcement

- Add checks in CI (future): verify `# CT_VENV:` header for Python scripts that touch governance paths.
- For now, rely on review policy + reviewer checks.  

Exceptions

- System-level tooling and OS packages remain outside venvs by design (e.g., systemd, net tools).