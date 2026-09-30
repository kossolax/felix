"""Animations du vrai manifeste sur des planches factices (cellules 50×40, entièrement opaques)."""
import json
from pathlib import Path

from felix.core.manifest import load_manifest

MANIFEST = Path(__file__).resolve().parent.parent / "sprites" / "felix.json"
CELL = (50, 40)


def make_anims():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sizes = {int(k): (cols * CELL[0], rows * CELL[1]) for k, (cols, rows) in data["sheets"].items()}
    return load_manifest(data, sizes, lambda sheet, rect: (0, 0, rect[2], rect[3]))
