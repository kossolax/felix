from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from felix.render.sprites import SpriteBank, opaque_bbox

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / "assets" / "original"


def image_with_block(x0, y0, x1, y1, size=(10, 10)):
    img = QImage(size[0], size[1], QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    for y in range(y0, y1):
        for x in range(x0, x1):
            img.setPixelColor(x, y, QColor(255, 255, 255, 255))
    return img


def test_opaque_bbox_is_exclusive_on_the_far_side():
    img = image_with_block(2, 3, 6, 8)
    assert opaque_bbox(img, (0, 0, 10, 10)) == (2, 3, 6, 8)


def test_opaque_bbox_is_relative_to_the_cell():
    img = image_with_block(12, 3, 14, 5, size=(20, 10))
    assert opaque_bbox(img, (10, 0, 10, 10)) == (2, 3, 4, 5)


def test_opaque_bbox_of_empty_cell_is_none():
    img = image_with_block(0, 0, 0, 0)
    assert opaque_bbox(img, (0, 0, 10, 10)) is None


@pytest.mark.skipif(not ORIGINAL.exists(), reason="sprites d'origine non extraits")
def test_real_manifest_matches_the_extracted_sheets(qapp):
    bank = SpriteBank.load(ROOT / "sprites" / "felix.json", ORIGINAL)
    assert len(bank.animations) >= 60
    walk = bank.animations["walk_right"]
    pix = bank.pixmap(walk.frames[0])
    assert (pix.width(), pix.height()) == walk.frames[0].rect[2:]
    assert bank.pixmap(walk.frames[0], mirrored=True).size() == pix.size()
