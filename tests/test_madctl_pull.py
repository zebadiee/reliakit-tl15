import os
import subprocess
import sys
import tempfile
from pathlib import Path

PY = sys.executable
ENV = {"PYTHONPATH": os.getcwd(), **os.environ}


def _init_git_repo(path: Path, filename: str = "README.md") -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init"], check=True)
    # config user if not set
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "testuser"], check=True)
    (path / filename).write_text("initial")
    subprocess.run(["git", "-C", str(path), "add", filename], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "initial"], check=True)


def run(cmd, env=None):
    return subprocess.run([PY, "-m", "mad_os.cli.madctl", *cmd], capture_output=True, text=True, env={**ENV, **(env or {})})


def test_pull_repos_initial_commit():
    with tempfile.TemporaryDirectory() as srcdir, tempfile.TemporaryDirectory() as rootdir:
        s1 = Path(srcdir) / "repo1"
        s2 = Path(srcdir) / "repo2"
        _init_git_repo(s1)
        _init_git_repo(s2)

        # file:// URLs
        url1 = f"file://{s1.resolve()}"
        url2 = f"file://{s2.resolve()}"

        res = run(["pull", "repos", "--repo", url1, "--repo", url2, "--root", rootdir, "--json"])
        assert res.returncode == 0, res.stderr

        # check snapshots
        d1 = Path(rootdir) / s1.name / ".mad_os" / "SNAPSHOT.txt"
        d2 = Path(rootdir) / s2.name / ".mad_os" / "SNAPSHOT.txt"
        assert d1.exists()
        assert d2.exists()
        txt1 = d1.read_text()
        assert "commit=" in txt1

        # audit log should exist and include this operation
        audit = Path(rootdir) / ".mad_os" / "AUDIT.log"
        assert audit.exists()
        import json
        lines = audit.read_text().splitlines()
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["action"] == "pull.repos"
        assert entry["root"] == rootdir
        assert any(r.get("url") == url1 and r.get("commit") for r in entry["repos"])


def test_pull_repos_update_commit():
    with tempfile.TemporaryDirectory() as srcdir, tempfile.TemporaryDirectory() as rootdir:
        s1 = Path(srcdir) / "repo1"
        _init_git_repo(s1)

        url1 = f"file://{s1.resolve()}"
        res = run(["pull", "repos", "--repo", url1, "--root", rootdir])
        assert res.returncode == 0
        snap = Path(rootdir) / s1.name / ".mad_os" / "SNAPSHOT.txt"
        assert snap.exists()
        before = snap.read_text()
        assert "commit=" in before

        # create new commit in source
        (s1 / "more.txt").write_text("more")
        subprocess.run(["git", "-C", str(s1), "add", "more.txt"], check=True)
        subprocess.run(["git", "-C", str(s1), "commit", "-m", "more"], check=True)

        # pull again
        res2 = run(["pull", "repos", "--repo", url1, "--root", rootdir])
        assert res2.returncode == 0
        after = snap.read_text()
        assert before != after

        # audit should reflect the updated commit for the repo
        audit = Path(rootdir) / ".mad_os" / "AUDIT.log"
        assert audit.exists()
        import json
        lines = audit.read_text().splitlines()
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        # extract commit from snapshot
        commit_after = None
        for line in after.splitlines():
            if line.startswith("commit="):
                commit_after = line.split("=", 1)[1].strip()
        assert commit_after
        repo_entry = next((r for r in entry["repos"] if r.get("url") == url1), None)
        assert repo_entry is not None
        assert repo_entry.get("commit") == commit_after
