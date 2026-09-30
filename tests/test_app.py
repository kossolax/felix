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
