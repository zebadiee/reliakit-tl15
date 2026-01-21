Title: feat(madctl): add audited repo ingestion syscall (pull.repos)

Summary:
- Introduces `madctl pull repos` as a read-only ingestion syscall for MAD-OS.
- Uses subprocess `git` only (no library side effects).
- Writes per-repo snapshot at `<root>/<repo>/.mad_os/SNAPSHOT.txt` (name, repo, branch, commit, pulled_at, mode=READ_ONLY).
- Appends an audit record to `<root>/.mad_os/AUDIT.log` as JSONL (ts, actor, action, mode, repos, root, sha).

Why:
- Establishes an auditable, deterministic repo ingestion primitive as the first MAD-OS syscall.
- Enables safe archaeology and adapter planning without executing repository code.

How:
- `mad_os/cli/madctl.py` implements `pull repos`.
  - `--repo` repeatable flag accepts repository URLs (supports `file://` for local repos).
  - `--file` accepts a path containing repo URLs, one per line.
  - `--root` sets the archeology root (default `$HOME/mad-os-research`).
  - `--json` emits a JSON summary of the operation.
- Append-only audit log is written to `<root>/.mad_os/AUDIT.log` with SHA256 envelope.

Safety guarantees:
- Import-safe: nothing happens at import time.
- No remote execution of repo code, no dependency installs.
- Idempotent and repeatable; subsequent pulls update snapshots and append audit entries.

Tests:
- `tests/test_madctl_pull.py`:
  - `test_pull_repos_initial_commit`: asserts snapshot and audit entries are created for two local file:// repos.
  - `test_pull_repos_update_commit`: asserts that a new commit in the source repo results in an updated snapshot and an appended audit entry reflecting the new commit.

CI:
- `.github/workflows/test-mad-os.yml` triggers on `mad_os/**`, `tests/**`, and `scripts/**` for PRs.

Notes & follow-ups:
- Consider adding signing/envelope for audit entries (future work).
- Implement `madctl status` to report last audit entry and mode.
- Create adapter binding PRs (Brakel, gh-ai-assistant, ai-cli-sphere) separately.

Obsidian archaeology note: `~/Obsidian/CT/RESEARCH/GITHUB_ARCHAEOLOGY.md` (contains scans and planned adapters for selected repos).

PR will be opened as draft: https://github.com/zebadiee/reliakit-tl15/pull/new/mad-os/madctl-pull
