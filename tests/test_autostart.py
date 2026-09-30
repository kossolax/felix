import sys

import pytest

from felix import autostart


@pytest.mark.skipif(sys.platform == "win32", reason="Linux")
def test_linux_autostart_writes_and_removes_a_desktop_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert not autostart.is_enabled()
    autostart.enable()
    entry = tmp_path / "autostart" / "virtual-felix.desktop"
    text = entry.read_text()
    assert "Exec=" in text and "X-GNOME-Autostart-Delay=" in text
    assert autostart.is_enabled()
    autostart.disable()
    assert not entry.exists() and not autostart.is_enabled()


def test_command_line_for_a_source_checkout():
    exe, args, workdir = autostart.command()
    if getattr(sys, "frozen", False):
        assert args == []
    else:
        assert exe == sys.executable and args == ["-m", "felix"] and (workdir / "felix").is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows")
def test_windows_autostart_uses_the_run_key(monkeypatch):
    monkeypatch.setattr(autostart, "RUN_KEY", r"Software\felix-test\Run")
    try:
        autostart.enable()
        assert autostart.is_enabled()
    finally:
        autostart.disable()
    assert not autostart.is_enabled()
