import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not (ROOT / "assets" / "original" / "fig_100.png").exists(), reason="sprites non extraits")
def test_selftest_runs_the_whole_app_headless(tmp_path):
    # dossiers utilisateur temporaires : ni journal ni réglages réels touchés
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_DATA_HOME=str(tmp_path / "data"),
               XDG_CONFIG_HOME=str(tmp_path / "config"), LOCALAPPDATA=str(tmp_path / "local"),
               FELIX_ASSETS=str(ROOT / "assets" / "original"))
    out = subprocess.run([sys.executable, "-m", "felix", "--selftest"], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "selftest ok" in out.stdout
