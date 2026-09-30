"""Extension Feeding côté appli : la boîte, la brique ou le sachet au bout du curseur."""
import random
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QSettings

from felix.core.world import Monitor, Rect, WorldSnapshot
from felix.platform.fake import FakeBackend

ROOT = Path(__file__).resolve().parent.parent
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


def test_the_kitten_can_be_shown_from_the_menu_and_has_its_own_window(bank, tmp_path):
    app, _ = make_app(bank, tmp_path)
    action(app, "Montrer le chaton")[1](False)
    for _ in range(40 * 30):
        app.tick(1 / 30)
        if app.pet.kitten is not None and app.pet.kitten.visible:
            break
    ticks(app, 0.2)
    assert app.kitten_window.isVisible()
    labels = [item[0] for item in app.menu_actions() if item]
    assert "Cacher le chaton" in labels and "Montrer le chaton" not in labels
    action(app, "Cacher le chaton")[1](False)
    ticks(app, 10)
    assert app.pet.kitten is None and not app.kitten_window.isVisible()


def test_the_held_item_is_cut_to_its_shape_but_catches_clicks_at_the_cursor(bank, tmp_path):
    app, _ = make_app(bank, tmp_path)
    app.held._use_mask = True  # comme sous X11 : sans compositeur, pas de rectangle noir autour
    for label in ("Pâtée Felix", "Lait Felix", "Friandises Felix"):
        action(app, label)[1](False)
        ticks(app, 0.5)
        held = app.held
        mask = held.mask()
        assert not mask.isEmpty() and mask.boundingRect() != held.rect() or mask.rectCount() > 1, label
        assert mask.contains(QPoint(*held.anchor)), label  # le point du curseur reste cliquable
        app.held.click_right()
        ticks(app, 2)


def test_a_click_does_not_take_the_food_while_the_cat_is_busy(bank, tmp_path):
    app, _ = make_app(bank, tmp_path)
    app.pet.request("tv")
    ticks(app, 1)
    assert app.pet.scene == "tv"
    action(app, "Pâtée Felix")[1](False)
    ticks(app, 0.5)
    app.held.click_left(1500, 400)
    ticks(app, 0.5)
    assert app.held.isVisible() and app.pet.holding == "can"  # toujours au curseur : il viendra après la télé


def test_the_bag_finishes_tipping_back_before_going_away(bank, tmp_path):
    app, backend = make_app(bank, tmp_path)
    action(app, "Friandises Felix")[1](False)
    ticks(app, 0.5)
    seen = []
    for x in (1200, 1400, 700):
        backend.set(snap((x, 500)))
        ticks(app, 0.2)
        app.held.click_left(x, 500)
        for _ in range(45):
            app.tick(1 / 30)
            seen.append(app.held._anim.name if app.held._anim is not None else None)
    last = seen[max(i for i, n in enumerate(seen) if n == "treats_bag_pour"):]
    assert "treats_bag_up" in last  # il se redresse avant de s'en aller
