"""Emplacements des ressources (dev, exe PyInstaller, données utilisateur)."""
import os
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
MANIFEST = ROOT / "sprites" / "felix.json"
SPRITES = ROOT / "assets" / "original"  # planches d'origine, livrées avec l'appli (voir CREDITS.md)
SOUNDS = ROOT / "assets" / "sounds"


def user_data_dir(env=os.environ, platform=sys.platform):
    if platform == "win32":
        return Path(env.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "felix"
    base = env.get("XDG_DATA_HOME") or Path(env.get("HOME", Path.home())) / ".local" / "share"
    return Path(base) / "felix"
