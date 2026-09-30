from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from felix.core.world import Monitor, Rect, WorldSnapshot
from felix.platform.fake import FakeBackend

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "assets" / "original" / "fig_100.png").exists(),
                                reason="sprites non extraits")

SNAP = WorldSnapshot(monitors=(Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080)),))


@pytest.fixture(scope="module")
def bank(qapp):
    from felix.paths import MANIFEST
    from felix.render.sprites import SpriteBank
    return SpriteBank.load(MANIFEST, ROOT / "assets" / "original")


def make_app(bank, tmp_path):
    from felix.app import FelixApp
    settings = QSettings(str(tmp_path / "felix.ini"), QSettings.Format.IniFormat)
    return FelixApp(bank, FakeBackend(SNAP), settings=settings)


def action(app, label):
    return next(item for item in app.menu_actions() if item and item[0].startswith(label))


def test_menu_feeds_and_gives_milk(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.tick(1 / 30)
    action(app, "Nourrir")[1](False)
    action(app, "Donner du lait")[1](False)
    # le repas commence tout de suite, le lait attend son tour
    assert app.pet.scene == "feed"
    assert app.pet._requests == ["drink"]


def test_menu_shows_the_gauges(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.pet.needs.hunger, app.pet.needs.thirst = 0.8, 0.2
    labels = [item[0] for item in app.menu_actions() if item]
    assert any("Faim 80 %" in label and "Soif 20 %" in label for label in labels)


def test_needs_survive_a_restart(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.pet.needs.hunger = 0.77
    app.save()
    again = make_app(bank, tmp_path)
    assert again.pet.needs.hunger == pytest.approx(0.77, abs=0.01)


def test_click_without_moving_is_a_stroke_and_a_drag_is_a_grab(bank, tmp_path):
    from PySide6.QtCore import QPoint
    app = make_app(bank, tmp_path)
    for _ in range(120):
        app.tick(1 / 30)
    x, y = int(app.pet.body.x), int(app.pet.body.y) - 20
    app.window.grabbed.emit(QPoint(x, y))
    app.window.released.emit(QPoint(x + 2, y))
    assert app.pet.mode == "script" and app.pet.player.animation.name in ("sit_down", "turn_to_right")
    app.window.grabbed.emit(QPoint(x, y))
    app.window.dragged.emit(QPoint(x + 30, y - 40))
    assert app.pet.mode == "held"
    app.window.released.emit(QPoint(x + 30, y - 40))
    assert app.pet.mode == "falling"


def test_sound_toggle_is_remembered(bank, tmp_path):
    class Player:
        enabled = True
        def play(self, event):
            pass
    app = make_app(bank, tmp_path)
    app.sound = Player()
    action(app, "Sons")[1](False)
    assert app.sound.enabled is False
    assert app.settings.value("sound") in (False, "false")


def test_menu_offers_yarn_and_tv(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.tick(1 / 30)
    action(app, "Jouer avec la pelote")[1](False)
    action(app, "Regarder la télé")[1](False)
    assert app.pet.scene == "yarn" and app.pet._requests == ["tv"]


def test_prop_events_reach_the_prop_manager(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.dispatch(("claws", 300.0, 500, 700))
    assert len(app.props.windows) == 1
