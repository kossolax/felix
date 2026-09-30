"""Une même image, jouée par deux animations qui s'enchaînent, reste au même endroit (pas de saut)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def anims(qapp):
    from felix.paths import MANIFEST
    from felix.render.sprites import SpriteBank
    return SpriteBank.load(MANIFEST, ROOT / "assets" / "original").animations


@pytest.mark.parametrize("first, then, offset", [
    # même image : même place ; autre planche : décalage mesuré au pixel entre les deux dessins
    ("sit_down", "sit_front", (0, 0)), ("sit_back_down", "sit_back", (0, 0)), ("sit_back", "sit_back_up", (0, 0)),
    ("sit_down", "stroked", (19, -1)), ("sit_down", "head_ambient", (19, -1)),
    ("climb_top", "sit_back", (44, -5)),
])
def test_the_cat_does_not_jump_between_these_poses(anims, first, then, offset):
    """Origine de la cellule de `then` par rapport à celle de `first` (dernière image, décalage de fin compris)."""
    a, b = anims[first], anims[then]
    fa, fb = a.frames[-1], b.frames[0]
    assert ((fa.anchor[0] + a.shift[0]) - fb.anchor[0], fa.anchor[1] - fb.anchor[1])[0] == offset[0]


def test_cursor_poses_sit_where_the_cat_sat(anims):
    for name, expected in (("head_bottom_right", (28, 89)), ("paw_bottom_right", (28, 86))):
        assert anims[name].frames[0].anchor == expected, name
