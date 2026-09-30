from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "assets" / "original" / "fig_304.png").exists(),
                                reason="sprites non extraits")


@pytest.fixture(scope="module")
def bank(qapp):
    from felix.paths import MANIFEST
    from felix.render.sprites import SpriteBank
    return SpriteBank.load(MANIFEST, ROOT / "assets" / "original")


def make_box(bank, calls):
    from felix.render.toybox import ToyboxWindow
    return ToyboxWindow(bank, on_play=lambda x: calls.append(("play", x)), on_hide=lambda: calls.append(("hide",)),
                        on_moved=lambda x: calls.append(("moved", x)))


def test_box_stands_on_the_floor_centered_on_its_x(bank):
    box = make_box(bank, [])
    box.place(800, 1040)
    assert box.x() + box.width() // 2 == 800
    assert box.y() + box.height() == 1040


def test_box_opens_while_playing(bank):
    box = make_box(bank, [])
    closed = box.pixmap.cacheKey()
    box.set_open(True)
    assert box.pixmap.cacheKey() != closed
    box.set_open(False)
    assert box.pixmap.cacheKey() == closed


def test_box_menu_plays_with_the_yarn_near_the_box_or_puts_it_away(bank):
    calls = []
    box = make_box(bank, calls)
    box.place(800, 1040)
    actions = dict(box.menu_actions())
    actions["Jouer avec la pelote"]()
    actions["Ranger la boîte à jouets"]()
    assert calls == [("play", 800), ("hide",)]


def test_dragging_keeps_the_grab_point_under_the_pointer(bank):
    calls = []
    box = make_box(bank, calls)
    box.place(800, 1040)
    box.begin_drag(810)  # attrapée 10 px à droite du centre
    box.drag_to(1110)
    assert box.dragging and box.center_x == 1100 and box.y() + box.height() == 1040
    box.drag_to(700)
    assert box.center_x == 690
    box.end_drag()
    assert not box.dragging and calls == [("moved", 690)]
