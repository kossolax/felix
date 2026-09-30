"""Extension Fun and Games : la souris mécanique. Elle arrive en marchant, le chat la guette,
bondit, l'attrape et la retourne, joue avec, puis la relâche et la regarde s'en aller."""
import json
import random

from felix.core.ball import MOUSE
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.tuning import MOUSE_FROM, MOUSE_NEAR, MOUSE_SPEED
from felix.core.world import Monitor, Rect, WorldSnapshot
from tests.anim_helpers import CELL, MANIFEST, make_anims

MANIFEST_FUN = MANIFEST.parent / "extensions" / "fun.json"

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
SNAP = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)
DRAWN = {"mouse_near", "mouse_pounce", "mouse_play", "mouse_upright"}


def settled_pet(seed=5, x=None, anims=None):
    pet = Pet(anims or make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, SNAP)
    if x is not None:
        pet.body.x = x
    return pet


def game(seed, x=800, seconds=90):
    pet = settled_pet(seed, x)
    pet.request("mouse")
    trace, started = [], False
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, SNAP)
        trace.append((view, pet.body.x, pet.player.index))
        started |= pet.scene == "mouse"
        if started and pet.scene is None:
            break
    return pet, trace


def names(trace):
    return [v.animation for v, _x, _i in trace]


def test_the_mouse_walks_in_gets_caught_played_with_and_walks_away():
    for seed, x in ((0, 800), (1, 1500), (2, 300)):
        pet, trace = game(seed, x)
        seen = names(trace)
        order = ["mouse_notice", "mouse_near", "mouse_pounce", "mouse_play", "mouse_upright", "mouse_release"]
        assert [seen.index(n) for n in order] == sorted(seen.index(n) for n in order), seed
        assert pet.scene is None and pet.ball is None  # partie hors de l'écran


def test_the_free_mouse_hides_while_the_cat_draws_it():
    pet, trace = game(3)
    drawn = [v for v, _x, i in trace if v.animation in DRAWN or (v.animation == "mouse_release" and i < 13)]
    assert drawn and all(v.ball is None or not v.ball.visible for v in drawn)
    walking = [v.ball for v, _x, _i in trace if v.ball is not None and v.ball.visible]
    assert walking and {b.anim for b in walking} <= {"mouse_walk_left", "mouse_walk_right"}
    assert all(not b.grabbable for b in walking)


def test_the_mouse_comes_right_up_to_where_the_cat_draws_it():
    for seed, x in ((0, 800), (1, 1500)):
        pet, trace = game(seed, x)
        i = names(trace).index("mouse_near")
        before, cat_x, _ = trace[i - 1]
        side = -1 if trace[i][0].mirrored else 1
        assert before.ball.visible and abs(before.ball.x - (cat_x + side * MOUSE_NEAR)) <= 8
        assert before.ball.anim == ("mouse_walk_left" if side > 0 else "mouse_walk_right")  # vers le chat


def test_the_released_mouse_walks_off_from_under_the_paw():
    pet, trace = game(4)
    seen = names(trace)
    i = next(k for k, (v, _x, idx) in enumerate(trace) if v.animation == "mouse_release" and idx >= 13)
    view, cat_x, _ = trace[i]
    side = -1 if view.mirrored else 1
    assert view.ball.visible and abs(view.ball.x - (cat_x + side * MOUSE_FROM)) <= 8
    later = [v.ball.x for v, _x, _i in trace[i:i + 30] if v.ball is not None]
    speed = (later[-1] - later[0]) / ((len(later) - 1) * DT)
    assert abs(speed - side * MOUSE_SPEED) < 10
    assert "mouse_release" in seen


def test_the_mouse_cannot_be_picked_up():
    pet = settled_pet(1, 800)
    pet.request("mouse")
    for _ in range(int(8 / DT)):
        pet.update(DT, SNAP)
        if pet.ball is not None:
            break
    assert pet.ball is not None and pet.ball.kind is MOUSE
    pet.grab_ball()
    assert not pet.ball.held


def test_a_stray_mouse_walks_off_when_the_game_is_interrupted():
    pet = settled_pet(1, 800)
    pet.request("mouse")
    for _ in range(int(8 / DT)):
        pet.update(DT, SNAP)
        if pet.ball is not None:
            break
    pet.grab(pet.body.x, pet.body.y - 30)
    pet.release()
    for _ in range(int(60 / DT)):
        pet.update(DT, SNAP)
        if pet.ball is None or pet.ball.kind is not MOUSE:
            break
    assert pet.ball is None or pet.ball.kind is not MOUSE


def test_no_mouse_without_the_extension():
    anims = {k: v for k, v in make_anims().items() if not k.startswith("mouse_")}
    pet = settled_pet(1, 800, anims=anims)
    pet.request("mouse")
    for _ in range(int(5 / DT)):
        pet.update(DT, SNAP)
    assert pet.ball is None and pet.scene is None


def test_the_mouse_walks_in_from_off_screen_and_off_it_again():
    for seed, x in ((0, 1500), (1, 300)):
        pet, trace = game(seed, x)
        mice = [v.ball for v, _x, _i in trace if v.ball is not None]
        assert mice[0].x > 1920 if x > 960 else mice[0].x < 0, seed
        assert all(m.y == 1080 for m in mice), seed  # elle sort par le bord, sans tomber sous le sol


def test_the_cat_keeps_his_eye_on_the_mouse_until_it_is_close():
    pet, trace = game(3)
    seen = names(trace)
    waiting = seen[seen.index("mouse_notice"):seen.index("mouse_near")]
    assert set(waiting) == {"mouse_notice"}  # pas de retour à la pose debout, tête baissée


def test_playing_with_the_mouse_never_snaps_back_to_the_first_frame():
    cols = json.loads(MANIFEST_FUN.read_text(encoding="utf-8"))["sheets"]["513"][0]

    def cell(rect):
        return rect[0] // CELL[0] + rect[1] // CELL[1] * cols

    for seed in range(4):
        _pet, trace = game(seed)
        cells = [cell(v.frame.rect) for v, _x, _i in trace if v.animation in ("mouse_play", "mouse_upright")]
        steps = {(a, b) for a, b in zip(cells, cells[1:]) if a != b}
        assert (10, 0) not in steps and cells[-1] == 14, seed  # jusqu'au bout de la planche, sans saut
