"""Aligne des animations enchaînées : cherche le décalage entre la dernière image de A
et la première de B, et en déduit des ancrages cohérents (outil de dev).

  python tools/align.py cupboard_enter:23 cupboard_exit:0 ...
      NOM[:image] ; par défaut on compare la dernière image de A à la première de B.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from felix.paths import MANIFEST  # noqa: E402
from felix.render.sprites import SpriteBank  # noqa: E402
from felix.resources.atlas import best_offset  # noqa: E402


def mask_rows(bank, frame):
    img = bank.image(frame)
    w, h = img.width(), img.height()
    bits, bpl = bytes(img.constBits()), img.bytesPerLine()
    rows = []
    for y in range(h):
        alpha = bits[y * bpl + 3:y * bpl + 4 * w:4]
        rows.append(sum(1 << x for x, a in enumerate(alpha) if a))
    return rows


def main():
    app = QGuiApplication([])  # noqa: F841
    bank = SpriteBank.load(MANIFEST, ROOT / "assets" / "original")
    specs = []
    for arg in sys.argv[1:]:
        name, _, idx = arg.partition(":")
        specs.append((name, int(idx) if idx else None))
    for (a_name, a_idx), (b_name, b_idx) in zip(specs, specs[1:]):
        a, b = bank.animations[a_name], bank.animations[b_name]
        fa = a.frames[a_idx if a_idx is not None else -1]
        fb = b.frames[b_idx if b_idx is not None else 0]
        dx, dy = best_offset(mask_rows(bank, fa), mask_rows(bank, fb),
                             max_dx=max(fa.rect[2], fb.rect[2]) // 2, max_dy=12)
        print(f"{a_name} -> {b_name} : décalage ({dx}, {dy})  ancre A {fa.anchor} -> B {(fa.anchor[0] + dx, fa.anchor[1] + dy)}")


if __name__ == "__main__":
    main()
