"""Extension Feeding côté appli : la boîte, la brique ou le sachet au bout du curseur."""
import random
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from felix.core.world import Monitor, Rect, WorldSnapshot
from felix.platform.fake import FakeBackend

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "assets" / "original" / "fig_609.png").exists(),
                                reason="extension Feeding non extraite")
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))


def snap(cursor):
    return WorldSnapshot(monitors=(SCREEN,), cursor=cursor)


@pytest.fixture(scope="module")
def bank(qapp):
    from felix.paths import MANIFEST
    from felix.render.sprites import SpriteBank
    return SpriteBank.load(MANIFEST, ROOT / "assets" / "original")


def make_app(bank, tmp_path, cursor=(1500, 400)):
    from felix.app import FelixApp
    settings = QSettings(str(tmp_path / "felix.ini"), QSettings.Format.IniFormat)
    backend = FakeBackend(snap(cursor))
    app = FelixApp(bank, backend, settings=settings, rng=random.Random(0))
    for _ in range(60):
        app.tick(1 / 30)
    return app, backend


def action(app, label):
    return next(item for item in app.menu_actions() if item and item[0] == label)


def ticks(app, seconds):
    for _ in range(int(seconds * 30)):
        app.tick(1 / 30)


def test_the_food_is_in_the_menu_only_with_its_extension(bank, tmp_path):
    app, _ = make_app(bank, tmp_path)
    labels = [item[0] for item in app.menu_actions() if item]
    assert {"Pâtée Felix", "Lait Felix", "Friandises Felix"} <= set(labels)
    loaded = bank.extensions
    try:
        bank.extensions = ()
        labels = [item[0] for item in app.menu_actions() if item]
        assert "Pâtée Felix" not in labels
    finally:
        bank.extensions = loaded


def test_the_can_follows_the_cursor_and_a_click_serves_it(bank, tmp_path):
    app, backend = make_app(bank, tmp_path)
    action(app, "Pâtée Felix")[1](False)
    ticks(app, 0.5)
    held = app.held
    assert held.isVisible() and app.pet.holding == "can"
    ax, ay = held.anchor
    assert (held.x() + ax, held.y() + ay) == (1500, 400)
    backend.set(snap((1300, 500)))
    ticks(app, 0.2)
    assert (held.x() + ax, held.y() + ay) == (1300, 500)
    held.click_left(1300, 500)
    ticks(app, 1)
    assert not held.isVisible() and app.pet.holding is None
    assert app.pet._item_state == "eating"


def test_a_right_click_takes_the_milk_back(bank, tmp_path):
    app, _ = make_app(bank, tmp_path)
    action(app, "Lait Felix")[1](False)
    ticks(app, 0.5)
    app.held.click_right()
    ticks(app, 1)
    assert not app.held.isVisible() and app.pet.holding is None


def test_each_click_with_the_bag_drops_a_treat_three_at_most(bank, tmp_path):
    app, backend = make_app(bank, tmp_path)
    action(app, "Friandises Felix")[1](False)
    ticks(app, 0.5)
    for x in (1200, 1400, 700):
        backend.set(snap((x, 500)))
        ticks(app, 0.2)
        app.held.click_left(x, 500)
        ticks(app, 1.5)
    assert app.treats_dropped == 3
    ticks(app, 1)
    assert not app.held.isVisible() and app.pet.holding is None
    shown = [w for w in app.treat_windows if w.isVisible()]
    assert len(shown) == len([t for t in app.pet.treats if not t.taken])


def test_the_held_item_goes_away_when_the_cat_stops_waiting(bank, tmp_path):
    app, _ = make_app(bank, tmp_path)
    action(app, "Pâtée Felix")[1](False)
    ticks(app, 0.5)
    app.pet.stop_holding()
    ticks(app, 1)
    assert not app.held.isVisible()
