"""Banque de sprites : planches PNG + manifeste -> pixmaps et masques par image."""
import json
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QBitmap, QImage, QPixmap, QRegion, QTransform

from felix.core.manifest import load_manifest


def _argb(img):
    return img if img.format() == QImage.Format.Format_ARGB32 else img.convertToFormat(QImage.Format.Format_ARGB32)


def opaque_bbox(img, rect):
    """Boîte (x0, y0, x1, y1) des pixels non transparents d'une cellule, relative à la cellule."""
    img = _argb(img)
    x, y, w, h = rect
    bpl = img.bytesPerLine()
    bits = bytes(img.constBits())
    x0 = y0 = None
    x1 = y1 = 0
    for row in range(h):
        start = (y + row) * bpl + x * 4
        alpha = bits[start + 3:start + 4 * w:4]  # ARGB32 little-endian : B G R A
        left = len(alpha) - len(alpha.lstrip(b"\0"))
        if left == len(alpha):
            continue
        right = len(alpha.rstrip(b"\0"))
        x0 = left if x0 is None else min(x0, left)
        x1 = max(x1, right)
        y0 = row if y0 is None else y0
        y1 = row + 1
    return None if x0 is None else (x0, y0, x1, y1)


class SpriteBank:
    def __init__(self, sheets, animations, scale=1):
        self.sheets = sheets  # {id: QImage}, déjà agrandies
        self.animations = animations
        self.scale = scale
        self._pixmaps = {}
        self._masks = {}

    @classmethod
    def load(cls, manifest_path, images_dir, scale=1):
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        sheets = {}
        for key in data.get("sheets", {}):
            img = QImage(str(Path(images_dir) / f"fig_{key}.png"))
            if img.isNull():
                raise FileNotFoundError(f"planche fig_{key}.png introuvable dans {images_dir}")
            if scale != 1:  # pixel art : agrandissement entier, sans lissage
                img = img.scaled(img.width() * scale, img.height() * scale)
            sheets[int(key)] = _argb(img)
        sizes = {sid: (img.width(), img.height()) for sid, img in sheets.items()}
        anims = load_manifest(data, sizes, lambda sid, rect: opaque_bbox(sheets[sid], rect), scale=scale)
        return cls(sheets, anims, scale)

    def image(self, frame, mirrored=False):
        img = self.sheets[frame.sheet].copy(QRect(*frame.rect))
        return img.transformed(QTransform.fromScale(-1, 1)) if mirrored else img

    def pixmap(self, frame, mirrored=False):
        key = (frame.sheet, frame.rect, mirrored)
        if key not in self._pixmaps:
            self._pixmaps[key] = QPixmap.fromImage(self.image(frame, mirrored))
        return self._pixmaps[key]

    def mask(self, frame, mirrored=False):
        """Région opaque de l'image, pour QWidget.setMask (clics traversants sous X11)."""
        key = (frame.sheet, frame.rect, mirrored)
        if key not in self._masks:
            bitmap = QBitmap.fromImage(self.pixmap(frame, mirrored).toImage().createAlphaMask())
            self._masks[key] = QRegion(bitmap)
        return self._masks[key]
