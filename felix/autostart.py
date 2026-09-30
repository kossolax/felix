"""Lancement de Felix à l'ouverture de session (Linux : ~/.config/autostart ; Windows : clé Run)."""
import os
import shlex
import sys
from pathlib import Path

ENTRY_NAME = "virtual-felix.desktop"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "VirtualFelix"


def command():
    """(exécutable, arguments, dossier de travail) pour relancer Felix tel qu'il tourne."""
    if getattr(sys, "frozen", False):
        return sys.executable, [], Path(sys.executable).parent
    return sys.executable, ["-m", "felix"], Path(__file__).resolve().parent.parent


def _entry_path():
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "autostart" / ENTRY_NAME


def _desktop_entry():
    exe, args, workdir = command()
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Virtual Felix",
        "Comment=Le chat de bureau",
        f"Exec={shlex.join([exe, *args])}",
        f"Path={workdir}",
        "X-GNOME-Autostart-enabled=true",
        "X-GNOME-Autostart-Delay=5",
        "",
    ])


def is_enabled():
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, RUN_VALUE)
            return True
        except OSError:
            return False
    return _entry_path().exists()


def enable():
    if sys.platform == "win32":
        import winreg
        exe, args, _ = command()
        value = " ".join(f'"{part}"' for part in [exe, *args])
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, value)
        return
    path = _entry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_desktop_entry(), encoding="utf-8")


def disable():
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, RUN_VALUE)
        except OSError:
            pass
        return
    _entry_path().unlink(missing_ok=True)


def set_enabled(on):
    enable() if on else disable()
