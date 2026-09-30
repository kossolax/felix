"""Animations synthétiques couvrant tous les noms utilisés par le cerveau."""
import json
from pathlib import Path

from felix.core.anim import Animation, Frame

MANIFEST = Path(__file__).resolve().parent.parent / "sprites" / "felix.json"


def make_anims():
    specs = json.loads(MANIFEST.read_text(encoding="utf-8"))["animations"]
    anims = {}
    for name, spec in specs.items():
        frames = tuple(Frame(sheet=spec["sheet"], rect=(i * 50, 0, 50, 40), anchor=(25, 40)) for i in range(3))
        anims[name] = Animation(name=name, sheet=spec["sheet"], frames=frames, fps=spec.get("fps", 10),
                                loop=spec.get("loop", False), dx=spec.get("dx", 0),
                                facing=spec.get("facing", "front"), shift=tuple(spec.get("shift", (0, 0))))
    return anims
