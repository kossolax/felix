"""Visualiseur d'animations du manifeste (outil de dev).

  python tools/atlas_viewer.py                    # fenêtre : liste des animations + lecture
  python tools/atlas_viewer.py --export out.png walk_left sit_front
                                                  # bandes d'images avec la croix d'ancrage
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QListWidget, QWidget,  # noqa: E402
                               QCheckBox, QVBoxLayout, QLabel)

from felix.core.anim import Player  # noqa: E402
from felix.render.sprites import SpriteBank  # noqa: E402

BG = QColor(90, 110, 130)


def draw_cross(p, x, y):
    p.setPen(QColor(255, 40, 40))
    p.drawLine(x - 5, y, x + 5, y)
    p.drawLine(x, y - 5, x, y + 5)


def export(bank, names, out):
    rows = [bank.animations[n] for n in names]
    width = max(sum(f.rect[2] + 4 for f in a.frames) for a in rows) + 150
    height = sum(max(f.rect[3] for f in a.frames) + 20 for a in rows) + 10
    img = QImage(min(width, 6000), height, QImage.Format.Format_ARGB32)
    img.fill(BG)
    p = QPainter(img)
    y = 4
    for a in rows:
        p.setPen(Qt.GlobalColor.yellow)
        p.drawText(2, y + 12, f"{a.name} ({a.sheet})")
        x = 140
        for i, f in enumerate(a.frames):
            p.drawPixmap(x, y + 16, bank.pixmap(f))
            draw_cross(p, x + f.anchor[0], y + 16 + f.anchor[1])
            p.setPen(QColor(255, 255, 0, 70))
            p.drawRect(x, y + 16, f.rect[2] - 1, f.rect[3] - 1)
            x += f.rect[2] + 4
        y += max(f.rect[3] for f in a.frames) + 20
    p.end()
    img.save(str(out))


class Viewer(QWidget):
    def __init__(self, bank):
        super().__init__()
        self.bank = bank
        self.setWindowTitle("Felix — atlas")
        self.list = QListWidget()
        self.list.addItems(sorted(bank.animations))
        self.list.currentTextChanged.connect(self.select)
        self.mirror = QCheckBox("miroir")
        self.info = QLabel()
        self.canvas = QWidget()
        self.canvas.setMinimumSize(640, 320)
        self.canvas.paintEvent = self.paint_canvas
        side = QVBoxLayout()
        side.addWidget(self.list)
        side.addWidget(self.mirror)
        side.addWidget(self.info)
        lay = QHBoxLayout(self)
        lay.addLayout(side)
        lay.addWidget(self.canvas, 1)
        self.player = None
        self.x = 0.0
        self.timer = QTimer(self, interval=33, timeout=self.tick)
        self.timer.start()
        self.list.setCurrentRow(0)

    def select(self, name):
        self.player = Player(self.bank.animations[name])
        self.x = 0.0

    def tick(self):
        if not self.player:
            return
        steps = self.player.update(0.033)
        self.x += steps * self.player.animation.dx
        if abs(self.x) > 200:
            self.x = 0.0
        if self.player.finished:
            self.player = Player(self.player.animation)
        f = self.player.frame
        self.info.setText(f"image {self.player.index} ancre {f.anchor}")
        self.canvas.update()

    def paint_canvas(self, _event):
        p = QPainter(self.canvas)
        p.fillRect(self.canvas.rect(), BG)
        base = QPoint(self.canvas.width() // 2 + int(self.x), self.canvas.height() - 60)
        p.setPen(QColor(200, 200, 200))
        p.drawLine(0, base.y(), self.canvas.width(), base.y())
        if self.player:
            f = self.player.frame
            mirrored = self.mirror.isChecked()
            ax = f.rect[2] - f.anchor[0] if mirrored else f.anchor[0]
            p.drawPixmap(base.x() - ax, base.y() - f.anchor[1], self.bank.pixmap(f, mirrored))
            draw_cross(p, base.x(), base.y())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=ROOT / "sprites" / "felix.json")
    parser.add_argument("--images", default=ROOT / "assets" / "original")
    parser.add_argument("--export", type=Path)
    parser.add_argument("names", nargs="*")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    bank = SpriteBank.load(args.manifest, args.images)
    if args.export:
        export(bank, args.names or sorted(bank.animations), args.export)
        return
    viewer = Viewer(bank)
    viewer.show()
    app.exec()


if __name__ == "__main__":
    main()
