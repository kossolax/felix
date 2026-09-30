"""Dessine l'icône de l'appli (une empreinte de patte), sans reprendre les graphismes d'origine.

Écrit assets/icon/felix.png (256 px) et assets/icon/felix.ico (16 à 256 px).
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "icon"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def paw(size):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(250, 250, 250))
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 48 * s, 48 * s)
    p.setBrush(QColor(20, 20, 20))
    p.drawEllipse(QRectF(64 * s, 118 * s, 128 * s, 104 * s))  # coussinet
    for x, y, w, h in ((30, 76, 46, 58), (74, 34, 48, 62), (134, 34, 48, 62), (180, 76, 46, 58)):
        p.drawEllipse(QRectF(x * s, y * s, w * s, h * s))  # doigts
    p.end()
    return img


def png_bytes(img):
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def ico(images):
    """Fichier .ico dont chaque image est un PNG (format accepté depuis Windows Vista)."""
    import struct
    blobs = [png_bytes(img) for img in images]
    out = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    for img, blob in zip(images, blobs):
        side = img.width() % 256
        out += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    return out + b"".join(blobs)


def main():
    app = QGuiApplication([])  # noqa: F841
    OUT.mkdir(parents=True, exist_ok=True)
    images = [paw(s) for s in SIZES]
    images[-1].save(str(OUT / "felix.png"))
    (OUT / "felix.ico").write_bytes(ico(images))
    print(f"icône écrite dans {OUT}")


if __name__ == "__main__":
    sys.exit(main())
