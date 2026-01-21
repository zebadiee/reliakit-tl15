import subprocess
import sys
from pathlib import Path


def test_import_adapters_in_clean_cwd(tmp_path: Path):
    cwd = tmp_path
    cmd = [sys.executable, "-c", "import mad_os.adapters.ai_cli_sphere as a; import mad_os.adapters.gh_ai_assistant as b; print(a.describe().name, b.describe().name)"]
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "ai-cli-sphere gh-ai-assistant" in res.stdout
    assert list(cwd.iterdir()) == []
