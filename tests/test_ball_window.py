from pathlib import Path

import pytest

from felix.core.pet import BallView

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def bank(qapp):
    from felix.paths import MANIFEST
    from felix.render.sprites import SpriteBank
    return SpriteBank.load(MANIFEST, ROOT / "assets" / "original")


def make_window(bank, calls):
    from felix.render.ball import BallWindow
    return BallWindow(bank, on_grab=lambda: calls.append(("grab",)),
                      on_drag=lambda x, y: calls.append(("drag", x, y)),
                      on_throw=lambda vx, vy: calls.append(("throw", round(vx), round(vy))))


def test_the_ball_sits_on_its_contact_point(bank):
    win = make_window(bank, [])
    win.show_view(BallView(500, 1000, 0))
    anchor = bank.animations["yarn_ball"].frames[0].anchor
    assert win.isVisible()
    assert (win.x() + anchor[0], win.y() + anchor[1]) == (500, 1000)


def test_the_ball_turns_and_hides(bank):
    win = make_window(bank, [])
    win.show_view(BallView(500, 1000, 0))
    first = win.pixmap.cacheKey()
    win.show_view(BallView(520, 1000, 1))
    assert win.pixmap.cacheKey() != first
    win.show_view(BallView(520, 1000, 1, visible=False))
    assert not win.isVisible()
    win.show_view(BallView(520, 1000, 1))
    win.show_view(None)
    assert not win.isVisible()


def test_the_ball_can_be_grabbed_dragged_and_thrown(bank):
    calls = []
    win = make_window(bank, calls)
    win.show_view(BallView(500, 1000, 0))
    win.grab_at(510, 990, 0.0)  # attrapée 10 px à droite, 10 px au-dessus du point de contact
    win.drag_to(610, 900, 0.05)
    win.drag_to(710, 800, 0.1)
    win.release(0.1)
    assert calls == [("grab",), ("drag", 600, 910), ("drag", 700, 810), ("throw", 2000, -1900)]


def test_a_ball_held_still_before_release_just_drops(bank):
    calls = []
    win = make_window(bank, calls)
    win.show_view(BallView(500, 1000, 0))
    win.grab_at(500, 990, 0.0)
    win.drag_to(600, 900, 0.05)
    win.release(1.0)
    assert calls[-1] == ("throw", 0, 0)


def test_the_window_shows_whichever_ball_is_out(bank):
    win = make_window(bank, [])
    win.show_view(BallView(500, 1000, 0))
    small = win.pixmap.size()
    win.show_view(BallView(500, 1000, 0, anim="beach_ball"))
    anchor = bank.animations["beach_ball"].frames[0].anchor
    assert win.pixmap.width() > 2 * small.width()
    assert (win.x() + anchor[0], win.y() + anchor[1]) == (500, 1000)


def test_a_toy_that_cannot_be_picked_up_ignores_the_mouse(bank, qapp):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    calls = []
    win = make_window(bank, calls)
    win.show_view(BallView(500, 1000, 0, grabbable=False))
    press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(505, 995),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    win.mousePressEvent(press)
    assert calls == [] and not win.dragging
