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


@pytest.mark.skipif(not ORIGINAL.exists(), reason="sprites d'origine non extraits")
def test_bank_can_be_loaded_twice_as_big(qapp):
    one = SpriteBank.load(ROOT / "sprites" / "felix.json", ORIGINAL)
    two = SpriteBank.load(ROOT / "sprites" / "felix.json", ORIGINAL, scale=2)
    f1, f2 = one.animations["walk_right"].frames[0], two.animations["walk_right"].frames[0]
    assert two.pixmap(f2).width() == 2 * one.pixmap(f1).width()
    assert two.animations["walk_right"].dx == 2 * one.animations["walk_right"].dx


def test_layered_frame_is_composed_with_the_layer_underneath(qapp):
    from felix.core.anim import Frame
    cat = QImage(10, 10, QImage.Format.Format_ARGB32)
    cat.fill(QColor(0, 0, 0, 0))
    cat.setPixelColor(5, 5, QColor(255, 0, 0, 255))
    tv = QImage(4, 4, QImage.Format.Format_ARGB32)
    tv.fill(QColor(0, 0, 255, 255))
    bank = SpriteBank({1: cat, 2: tv}, {})
    frame = Frame(1, (0, 0, 10, 10), (5, 9), under=((2, (0, 0, 4, 4), (4, -2)),))
    img = bank.pixmap(frame).toImage()
    assert (img.width(), img.height()) == (10, 12)  # la télé dépasse de 2 px au-dessus
    assert img.pixelColor(4, 0).getRgb() == (0, 0, 255, 255)  # télé
    assert img.pixelColor(5, 7).getRgb() == (255, 0, 0, 255)  # chat par-dessus
    assert img.pixelColor(0, 5).alpha() == 0


def test_plain_and_layered_versions_of_a_cell_are_cached_separately(qapp):
    from felix.core.anim import Frame
    cat = QImage(10, 10, QImage.Format.Format_ARGB32)
    cat.fill(QColor(255, 0, 0, 255))
    tv = QImage(4, 4, QImage.Format.Format_ARGB32)
    tv.fill(QColor(0, 0, 255, 255))
    bank = SpriteBank({1: cat, 2: tv}, {})
    layered = Frame(1, (0, 0, 10, 10), (5, 9), under=((2, (0, 0, 4, 4), (4, -2)),))
    plain = Frame(1, (0, 0, 10, 10), (5, 9))
    assert bank.pixmap(layered).height() == 12
    assert bank.pixmap(plain).height() == 10  # pas la version avec télé
    assert bank.mask(plain).boundingRect().height() == 10
