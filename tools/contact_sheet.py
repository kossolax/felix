"""Assemble des PNG sur un fond gris avec leur nom (outil de dev).

Usage : python tools/contact_sheet.py sortie.png fig_100.png fig_101.png ...
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402


def main():
    out, paths = sys.argv[1], sys.argv[2:]
    app = QGuiApplication([])  # noqa: F841
    images = [(os.path.basename(p), QImage(p)) for p in paths]
    pad, label = 8, 16
    width = sum(img.width() + pad for _, img in images) + pad
    height = max(img.height() for _, img in images) + label + 2 * pad
    sheet = QImage(width, height, QImage.Format.Format_ARGB32)
    sheet.fill(QColor(90, 110, 130))
    p = QPainter(sheet)
    p.setPen(Qt.GlobalColor.yellow)
    x = pad
    for name, img in images:
        p.drawText(x, pad + 11, name)
        p.drawImage(x, pad + label, img)
        p.setPen(QColor(255, 255, 0, 90))
        p.drawRect(x - 1, pad + label - 1, img.width() + 1, img.height() + 1)
        p.setPen(Qt.GlobalColor.yellow)
        x += img.width() + pad
    p.end()
    sheet.save(out)


if __name__ == "__main__":
    main()
