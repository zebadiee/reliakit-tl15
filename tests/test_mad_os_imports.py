import subprocess
import sys
from pathlib import Path


def test_import_mad_os_in_clean_cwd(tmp_path: Path):
    """Importing mad_os modules in an empty cwd must not create files or exit."""
    cwd = tmp_path
    cmd = [sys.executable, "-c", "import mad_os; import mad_os.core.mode; print('OK')"]
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "OK" in res.stdout
    # ensure no files were created in cwd
    assert list(cwd.iterdir()) == []
