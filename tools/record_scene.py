"""Enregistre une scène du chat hors écran, image par image, en planche contact (outil de dev).

  python tools/record_scene.py tv out.png [--seconds 30] [--every 3] [--seed 1] [--crop 900x300 --cols 3]

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
CROP = (240, 260)  # par défaut, autour des pieds de départ (assez haut pour les bonds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("scene")
    p.add_argument("out", type=Path)
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--every", type=int, default=3, help="une image sur N ticks")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--only", default="", help="animations à garder (préfixes, séparés par des virgules)")
    p.add_argument("--crop", default=f"{CROP[0]}x{CROP[1]}", help="taille de chaque vignette, LxH")
    p.add_argument("--cols", type=int, default=8)
    p.add_argument("--x", type=float, help="abscisse du chat au départ")
    args = p.parse_args()
    crop = tuple(int(v) for v in args.crop.split("x"))
    app = QGuiApplication([])  # noqa: F841
    bank = SpriteBank.load(MANIFEST, ROOT / "assets" / "original")
    ext = compute_extents(bank.animations)
    pet = Pet(bank.animations, rng=random.Random(args.seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, WORLD)
    if args.x is not None:
        pet.body.x = args.x
    served = args.scene in ("can", "carton", "treats")  # objets tenus au curseur (extension Feeding)
    if served:
        pet.hold_item(args.scene)
    elif args.scene.startswith("kitten_") and args.scene != "kitten_show":  # scène à deux : le chaton d'abord
        pet.show_kitten()
        for _ in range(int(40 / DT)):
            pet.update(DT, WORLD)
            if pet.kitten is not None and pet.scene is None:
                break
        pet.request(args.scene)
    else:
        pet.request(args.scene)
    origin = None
    shots = []
    keep = tuple(filter(None, args.only.split(",")))
    for tick in range(int(args.seconds / DT)):
        if served and tick == int(3 / DT):  # on sert au bout de 3 s ; le sachet : trois friandises
            if args.scene == "treats":
                for dx in (180, -150, 90):
                    pet.drop_treat(pet.body.x + dx, pet.body.y - 200)
                pet.stop_holding()
            else:
                pet.serve()
        view = pet.update(DT, WORLD)
        if origin is None:
            origin = (round(view.x) - crop[0] // 2, round(view.y) - crop[1] + 30)
        if tick % args.every or (keep and not view.animation.startswith(keep)):
            continue
        img = QImage(*crop, QImage.Format.Format_ARGB32)
        img.fill(QColor(90, 110, 130))
        painter = QPainter(img)
        wx, wy = ext.window_origin(view)
        ox, oy = ext.frame_offset(view.frame, view.mirrored)
        for treat in view.treats:
            if treat.visible:
                tf = bank.animations[treat.anim].frames[0]
                painter.drawPixmap(round(treat.x) - tf.anchor[0] - origin[0], round(treat.y) - tf.anchor[1] - origin[1],
                                   bank.pixmap(tf))
        if view.ball is not None and view.ball.visible:
            bf = bank.animations[view.ball.anim].frames[view.ball.frame]
            painter.drawPixmap(round(view.ball.x) - bf.anchor[0] - origin[0], round(view.ball.y) - bf.anchor[1] - origin[1],
                               bank.pixmap(bf))
        painter.drawPixmap(wx + ox - origin[0], wy + oy - origin[1], bank.pixmap(view.frame, view.mirrored))
        kitten = view.kitten  # devant Felix, comme sa fenêtre
        if kitten is not None and kitten.visible:
            kf = bank.animations[kitten.anim].frames[kitten.frame]
            painter.drawPixmap(round(kitten.x) - kf.anchor[0] - origin[0], round(kitten.y) - kf.anchor[1] - origin[1],
                               bank.pixmap(kf))
        painter.setPen(QPen(QColor(255, 60, 60), 1))
        fx, fy = round(view.x) - origin[0], round(view.y) - origin[1]
        painter.drawLine(fx - 4, fy, fx + 4, fy)
        painter.setPen(Qt.GlobalColor.yellow)
        painter.drawText(3, 12, f"{tick * DT:5.1f}s {view.animation}[{pet.player.index}]")
        painter.end()
        shots.append(img)
    cols = args.cols
    rows = (len(shots) + cols - 1) // cols
    sheet = QImage(cols * (crop[0] + 2), max(rows, 1) * (crop[1] + 2), QImage.Format.Format_ARGB32)
    sheet.fill(QColor(30, 30, 30))
    painter = QPainter(sheet)
    for i, img in enumerate(shots):
        painter.drawImage((i % cols) * (crop[0] + 2), (i // cols) * (crop[1] + 2), img)
    painter.end()
    sheet.save(str(args.out))
    print(f"{len(shots)} images → {args.out}")


if __name__ == "__main__":
    main()
