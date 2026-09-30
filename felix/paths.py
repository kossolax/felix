"""Emplacements des ressources (dev, exe PyInstaller, données utilisateur)."""
import os
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
MANIFEST = ROOT / "sprites" / "felix.json"
SOUNDS = ROOT / "assets" / "sounds"


def user_data_dir(env=os.environ, platform=sys.platform):
    if platform == "win32":
        return Path(env.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "felix"
    base = env.get("XDG_DATA_HOME") or Path(env.get("HOME", Path.home())) / ".local" / "share"
    return Path(base) / "felix"


def default_candidates():
    return [ROOT / "assets" / "original", user_data_dir() / "original"]


def find_sprites_dir(env=os.environ, candidates=None):
    dirs = []
    if env.get("FELIX_ASSETS"):
        dirs.append(Path(env["FELIX_ASSETS"]))
    dirs.extend(candidates if candidates is not None else default_candidates())
    return next((Path(d) for d in dirs if (Path(d) / "fig_100.png").exists()), None)
