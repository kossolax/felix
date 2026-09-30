"""Enregistre une scène du chat hors écran, image par image, en planche contact (outil de dev).

  python tools/record_scene.py tv out.png [--seconds 30] [--every 3] [--seed 1]

Le vrai cerveau tourne sur un écran factice 1280×720 ; chaque image est dessinée à sa
position écran exacte (même calcul que la fenêtre du chat), recadrée autour des pieds.
"""
import argparse
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen  # noqa: E402

from felix.core.needs import Needs  # noqa: E402
from felix.core.pet import Pet  # noqa: E402
from felix.core.world import Monitor, Rect, WorldSnapshot  # noqa: E402
from felix.paths import MANIFEST  # noqa: E402
from felix.render.pet_window import compute_extents  # noqa: E402
from felix.render.sprites import SpriteBank  # noqa: E402

DT = 1 / 30
WORLD = WorldSnapshot(monitors=(Monitor(Rect(0, 0, 1280, 720), Rect(0, 0, 1280, 720)),))
CROP = (240, 260)  # autour des pieds de départ (assez haut pour les bonds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("scene")
    p.add_argument("out", type=Path)
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--every", type=int, default=3, help="une image sur N ticks")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--only", default="", help="animations à garder (préfixes, séparés par des virgules)")
    args = p.parse_args()
    app = QGuiApplication([])  # noqa: F841
    bank = SpriteBank.load(MANIFEST, ROOT / "assets" / "original")
    ext = compute_extents(bank.animations)
    pet = Pet(bank.animations, rng=random.Random(args.seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, WORLD)
    pet.request(args.scene)
    origin = None
    shots = []
    keep = tuple(filter(None, args.only.split(",")))
    for tick in range(int(args.seconds / DT)):
        view = pet.update(DT, WORLD)
        if origin is None:
            origin = (round(view.x) - CROP[0] // 2, round(view.y) - CROP[1] + 30)
        if tick % args.every or (keep and not view.animation.startswith(keep)):
            continue
        img = QImage(*CROP, QImage.Format.Format_ARGB32)
        img.fill(QColor(90, 110, 130))
        painter = QPainter(img)
        wx, wy = ext.window_origin(view)
        ox, oy = ext.frame_offset(view.frame, view.mirrored)
        painter.drawPixmap(wx + ox - origin[0], wy + oy - origin[1], bank.pixmap(view.frame, view.mirrored))
        painter.setPen(QPen(QColor(255, 60, 60), 1))
        fx, fy = round(view.x) - origin[0], round(view.y) - origin[1]
        painter.drawLine(fx - 4, fy, fx + 4, fy)
        painter.setPen(Qt.GlobalColor.yellow)
        painter.drawText(3, 12, f"{tick * DT:5.1f}s {view.animation}[{pet.player.index}]")
        painter.end()
        shots.append(img)
    cols = 8
    rows = (len(shots) + cols - 1) // cols
    sheet = QImage(cols * (CROP[0] + 2), max(rows, 1) * (CROP[1] + 2), QImage.Format.Format_ARGB32)
    sheet.fill(QColor(30, 30, 30))
    painter = QPainter(sheet)
    for i, img in enumerate(shots):
        painter.drawImage((i % cols) * (CROP[0] + 2), (i // cols) * (CROP[1] + 2), img)
    painter.end()
    sheet.save(str(args.out))
    print(f"{len(shots)} images → {args.out}")


if __name__ == "__main__":
    main()
