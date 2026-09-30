import random
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
    return FelixApp(bank, FakeBackend(SNAP), settings=settings, rng=random.Random(0))  # hasard reproductible


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


def test_the_cupboard_fades_on_screen_after_the_meal(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.tick(1 / 30)
    action(app, "Nourrir")[1](False)
    for _ in range(40 * 30):
        app.tick(1 / 30)
        if app.pet.scene is None:
            break
    ghosts = [w for w in app.props.windows if (w.width(), w.height()) == (215, 117)]
    assert len(ghosts) == 1 and ghosts[0].fade_ms <= 500


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


def test_menu_offers_the_goldfish(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.tick(1 / 30)
    action(app, "Regarder le poisson rouge")[1](False)
    assert app.pet.scene == "fishbowl"


def test_prop_events_reach_the_prop_manager(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.dispatch(("claws", 300.0, 500, 700))
    assert len(app.props.windows) == 1


def test_big_size_can_be_applied_live_for_tests(bank, tmp_path):
    from felix.paths import MANIFEST
    from felix.render.sprites import SpriteBank

    def loader(scale):
        return SpriteBank.load(MANIFEST, ROOT / "assets" / "original", scale=scale)

    app = make_app(bank, tmp_path)
    app.bank_loader = loader
    for _ in range(60):
        app.tick(1 / 30)
    width = app.window.width()
    app.set_scale(True)
    app.tick(1 / 30)
    assert app.pet.k == 2 and app.window.width() == 2 * width


def test_about_text_credits_the_original_and_the_sounds(bank, tmp_path):
    app = make_app(bank, tmp_path)
    text = app.about_text()
    assert "Felix II" in text and "Wikimedia" in text
    assert any(item and item[0].startswith("À propos") for item in app.menu_actions())


def test_tray_menu_mirrors_the_cat_menu(bank, tmp_path):
    from PySide6.QtWidgets import QMenu
    app = make_app(bank, tmp_path)
    menu = QMenu()
    app.fill_menu(menu)
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert labels[:2] == ["Nourrir", "Donner du lait"] and labels[-1] == "Quitter"


def test_speed_scales_time_for_tests(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.tick(0.03)
    before = app.pet.clock
    app.set_speed(1.6)
    app.tick(0.03)
    assert app.pet.clock - before == pytest.approx(0.03 * 1.6)


def test_size_and_speed_are_not_in_the_menu_nor_remembered(bank, tmp_path):
    app = make_app(bank, tmp_path)
    labels = [item[0] for item in app.menu_actions() if item]
    assert not [label for label in labels if "Vitesse" in label or "taille" in label]
    app.settings.setValue("speed", 1.6)  # réglages d'une ancienne version
    again = make_app(bank, tmp_path)
    assert again.speed == 1.0


def test_quit_lets_the_cat_leave_through_its_flap_first(bank, tmp_path):
    app = make_app(bank, tmp_path)
    for _ in range(150):
        app.tick(1 / 30)
    app.request_quit()
    assert app.pet.scene == "leave" and not app.quitting_done  # (il peut d'abord se retourner)
    seen = set()
    for _ in range(150):
        if app.tick(1 / 30) is not None:
            seen.add(app.pet.player.animation.name)
    assert "exit_flap" in seen and app.quitting_done


def test_toybox_is_put_away_at_each_start_but_keeps_its_place(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.tick(1 / 30)
    assert not app.toybox.isVisible()
    action(app, "Boîte à jouets")[1](True)
    app.tick(1 / 30)
    assert app.toybox.isVisible()
    assert app.toybox.y() + app.toybox.height() == 1080  # posée sur le sol
    drag(app, app.toybox.center_x, 700)
    app.quit()
    again = make_app(bank, tmp_path)
    again.tick(1 / 30)
    assert not again.toybox.isVisible()
    action(again, "Boîte à jouets")[1](True)
    again.tick(1 / 30)
    assert again.toybox.center_x == 700


def settled_app(bank, tmp_path, box=True):
    app = make_app(bank, tmp_path)
    for _ in range(120):
        app.tick(1 / 30)
    if box:
        action(app, "Boîte à jouets")[1](True)
        app.tick(1 / 30)
    return app


def test_playing_from_the_toybox_pops_the_ball_out_until_the_game_ends(bank, tmp_path):
    app = settled_app(bank, tmp_path)
    app.toybox.on_play(app.toybox.center_x)
    ball = app.pet.ball
    assert ball is not None and ball.home == "box"
    assert abs(ball.x - app.toybox.center_x) < app.toybox.width() // 2 and ball.y < app.toybox.floor_y
    app.tick(1 / 30)
    assert app.toybox._open and app.ball_window.isVisible()
    for _ in range(int(150 * 30)):
        app.tick(1 / 30)
        if app.pet.ball is None and app.pet.scene is None:
            break
    app.tick(1 / 30)
    assert app.pet.ball is None and not app.toybox._open and not app.ball_window.isVisible()


def test_putting_the_toybox_away_puts_its_ball_away_too(bank, tmp_path):
    app = settled_app(bank, tmp_path)
    app.toybox.on_play(app.toybox.center_x)
    app.tick(1 / 30)
    action(app, "Boîte à jouets")[1](False)
    app.tick(1 / 30)
    assert app.pet.ball is None and not app.ball_window.isVisible()


def test_the_ball_can_be_thrown_with_the_mouse(bank, tmp_path):
    app = settled_app(bank, tmp_path, box=False)
    action(app, "Jouer avec la pelote")[1](False)
    for _ in range(int(20 * 30)):
        app.tick(1 / 30)
        if app.pet.ball is not None and app.pet.ball.resting and app.ball_window.isVisible():
            break
    win, ball = app.ball_window, app.pet.ball
    win.grab_at(ball.x, ball.y - 10, 0.0)
    assert ball.held
    win.drag_to(ball.x + 50, 700, 0.05)
    win.drag_to(ball.x + 100, 650, 0.1)
    win.release(0.1)
    assert not ball.held and ball.vx > 0 and ball.vy < 0


def test_dropping_the_ball_on_its_box_puts_it_away(bank, tmp_path):
    app = settled_app(bank, tmp_path)
    app.toybox.on_play(app.toybox.center_x)
    for _ in range(int(3 * 30)):
        app.tick(1 / 30)
    win, box = app.ball_window, app.toybox
    win.grab_at(app.pet.ball.x, app.pet.ball.y - 10, 0.0)
    win.drag_to(box.center_x, box.y() + 5, 1.0)
    win.release(2.0)
    app.tick(1 / 30)
    assert app.pet.ball is None and not app.toybox._open


def two_screens(side_by_side=True):
    first = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
    second = (Monitor(Rect(1920, 0, 1920, 1080), Rect(1920, 0, 1920, 1080)) if side_by_side
              else Monitor(Rect(0, 1080, 1920, 1080), Rect(0, 1080, 1920, 1080)))
    return WorldSnapshot(monitors=(first, second))


def drag(app, box_from, box_to, steps=20):
    app.toybox.begin_drag(box_from)
    for i in range(1, steps + 1):
        app.toybox.drag_to(box_from + (box_to - box_from) * i // steps)
        app.tick(1 / 30)  # la boucle tourne pendant le glisser
    app.toybox.end_drag()
    app.tick(1 / 30)


def test_the_app_loop_never_fights_a_drag_and_saves_what_is_shown(bank, tmp_path):
    app = make_app(bank, tmp_path)
    action(app, "Boîte à jouets")[1](True)
    app.tick(1 / 30)
    start = app.toybox.center_x
    drag(app, start, start + 200)
    assert app.toybox.center_x == start + 200
    assert int(app.settings.value("toybox/x")) == app.toybox.center_x


def test_the_box_can_be_dragged_onto_the_next_monitor(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.backend.set(two_screens())
    action(app, "Boîte à jouets")[1](True)
    app.tick(1 / 30)
    drag(app, app.toybox.center_x, 2600)
    assert app.toybox.center_x == 2600 and int(app.settings.value("toybox/x")) == 2600


def test_dropping_past_the_outer_edge_clamps_to_the_nearest_monitor(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.backend.set(two_screens())
    action(app, "Boîte à jouets")[1](True)
    app.tick(1 / 30)
    drag(app, app.toybox.center_x, 4200)  # au-delà du bord droit du 2e écran
    half = app.toybox.width() // 2
    assert app.toybox.center_x == 3840 - half
    assert int(app.settings.value("toybox/x")) == app.toybox.center_x


def test_stacked_monitors_keep_the_box_on_the_screen_it_was_put_on(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.backend.set(two_screens(side_by_side=False))
    app.settings.setValue("toybox/x", 500)
    app.settings.setValue("toybox/floor", 2160)  # écran du bas
    action(app, "Boîte à jouets")[1](True)
    for _ in range(3):
        app.tick(1 / 30)
    assert app.toybox.floor_y == 2160


def test_the_box_comes_back_when_its_monitor_is_plugged_again(bank, tmp_path):
    app = make_app(bank, tmp_path)
    app.backend.set(two_screens())
    action(app, "Boîte à jouets")[1](True)
    app.tick(1 / 30)
    drag(app, app.toybox.center_x, 3000)
    app.backend.set(SNAP)  # écran externe débranché
    app.tick(1 / 30)
    assert app.toybox.center_x < 1920
    app.backend.set(two_screens())  # rebranché
    app.tick(1 / 30)
    assert app.toybox.center_x == 3000


def test_sprites_are_reloaded_when_extensions_arrive(bank, tmp_path):
    from felix.app import FelixApp
    calls = []

    def loader(scale):
        calls.append(scale)
        return bank

    settings = QSettings(str(tmp_path / "felix.ini"), QSettings.Format.IniFormat)
    app = FelixApp(bank, FakeBackend(SNAP), settings=settings, bank_loader=loader)
    app.tick(1 / 30)
    app.reload_sprites()
    assert calls == [1] and app.bank is bank and app.pet.anims is bank.animations
