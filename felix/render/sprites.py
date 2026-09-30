"""Banque de sprites : planches PNG + manifeste -> pixmaps et masques par image."""
import json
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBitmap, QImage, QPixmap, QRegion, QTransform

from PySide6.QtGui import QPainter

from felix.core.anim import frame_bounds
from felix.core.manifest import load_manifest, merge_manifests


def _argb(img):
    return img if img.format() == QImage.Format.Format_ARGB32 else img.convertToFormat(QImage.Format.Format_ARGB32)


def _erase(img, rects, scale):
    """Rend transparentes des zones de la planche (ex. la pelote dessinée, remplacée par la vraie)."""
    if not rects:
        return img
    p = QPainter(img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    for x, y, w, h in rects:
        p.fillRect(x * scale, y * scale, w * scale, h * scale, Qt.GlobalColor.transparent)
    p.end()
    return img


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
    def __init__(self, sheets, animations, scale=1, extensions=()):
        self.sheets = sheets  # {id: QImage}, déjà agrandies
        self.animations = animations
        self.scale = scale
        self.extensions = extensions  # extensions chargées (fun, feeding…)
        self._pixmaps = {}
        self._masks = {}

    @classmethod
    def load(cls, manifest_path, images_dir, scale=1):
        """Le jeu, plus chaque extension (extensions/*.json à côté du manifeste) dont les planches
        ont été extraites."""
        manifest_path, images_dir = Path(manifest_path), Path(images_dir)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        extras = {}
        for path in sorted((manifest_path.parent / "extensions").glob("*.json")):
            extra = json.loads(path.read_text(encoding="utf-8"))
            if all((images_dir / f"fig_{key}.png").exists() for key in extra.get("sheets", {})):
                extras[path.stem] = extra
        data = merge_manifests(data, extras.values())
        sheets = {}
        for key in data.get("sheets", {}):
            img = QImage(str(Path(images_dir) / f"fig_{key}.png"))
            if img.isNull():
                raise FileNotFoundError(f"planche fig_{key}.png introuvable dans {images_dir}")
            if scale != 1:  # pixel art : agrandissement entier, sans lissage
                img = img.scaled(img.width() * scale, img.height() * scale)
            sheets[int(key)] = _erase(_argb(img), data.get("erase", {}).get(key, ()), scale)
        sizes = {sid: (img.width(), img.height()) for sid, img in sheets.items()}
        anims = load_manifest(data, sizes, lambda sid, rect: opaque_bbox(sheets[sid], rect), scale=scale)
        return cls(sheets, anims, scale, tuple(extras))

    def image(self, frame, mirrored=False):
        """Image de la cellule, avec ses couches éventuelles dessous et dessus (voir frame_bounds)."""
        img = self.sheets[frame.sheet].copy(QRect(*frame.rect))
        if frame.under or frame.over:
            x0, y0, x1, y1 = frame_bounds(frame)
            canvas = QImage(x1 - x0, y1 - y0, QImage.Format.Format_ARGB32)
            canvas.fill(0)
            p = QPainter(canvas)
            for sheet, rect, (ox, oy) in frame.under:
                p.drawImage(ox - x0, oy - y0, self.sheets[sheet].copy(QRect(*rect)))
            p.drawImage(-x0, -y0, img)
            for sheet, rect, (ox, oy) in frame.over:
                p.drawImage(ox - x0, oy - y0, self.sheets[sheet].copy(QRect(*rect)))
            p.end()
            img = canvas
        return img.transformed(QTransform.fromScale(-1, 1)) if mirrored else img

    def pixmap(self, frame, mirrored=False):
        key = (frame.sheet, frame.rect, frame.under, frame.over, mirrored)
        if key not in self._pixmaps:
            self._pixmaps[key] = QPixmap.fromImage(self.image(frame, mirrored))
        return self._pixmaps[key]

    def mask(self, frame, mirrored=False):
        """Région opaque de l'image, pour QWidget.setMask (clics traversants sous X11)."""
        key = (frame.sheet, frame.rect, frame.under, frame.over, mirrored)
        if key not in self._masks:
            img = self.pixmap(frame, mirrored).toImage()
            if img.hasAlphaChannel():
                self._masks[key] = QRegion(QBitmap.fromImage(img.createAlphaMask()))
            else:  # image entièrement opaque : Qt l'a convertie sans canal alpha
                self._masks[key] = QRegion(img.rect())
        return self._masks[key]
