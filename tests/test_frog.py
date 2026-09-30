"""Extension Fun and Games : la grenouille. Elle arrive en sautant ; le chat la guette et bondit,
elle lui échappe d'un saut à chaque fois, puis s'en va."""
import random

from felix.core.frog import FROG, Frog
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.surfaces import compute_surfaces
from felix.core.tuning import FROG_HOP
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
SNAP = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)


def settled_pet(seed=5, x=None, anims=None):
    pet = Pet(anims or make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, SNAP)
    if x is not None:
        pet.body.x = x
    return pet


def game(seed, x=800, seconds=120):
    pet = settled_pet(seed, x)
    pet.request("frog")
    trace, started = [], False
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, SNAP)
        trace.append((view, pet.body.x))
        started |= pet.scene == "frog"
        if started and pet.scene is None:
            break
    return pet, trace


def test_a_frog_hops_along_one_leap_at_a_time():
    segs = compute_surfaces(SNAP)
    frog = Frog(1000, 1080, heading=-1)
    frog.update(DT, SNAP, segs)
    frog.hop(3, pause=(0.2, 0.2))
    xs, anims = [], []
    for _ in range(int(3 / DT)):
        frog.update(DT, SNAP, segs)
        xs.append(frog.x)
        anims.append(frog.anim)
    assert abs(xs[-1] - (1000 - 3 * FROG_HOP[-1])) < 1
    assert "frog_hop_left" in anims and anims[-1] == "frog_sit_left"
    moving = [a for a, x0, x1 in zip(anims[1:], xs, xs[1:]) if x1 != x0]
    assert set(moving) == {"frog_hop_left"}  # elle n'avance qu'en sautant


def test_the_cat_leaps_at_the_frog_again_and_again_but_never_catches_it():
    for seed, x in ((0, 800), (1, 1500), (2, 300)):
        pet, trace = game(seed, x)
        seen = [v.animation for v, _x in trace]
        leaps = sum(1 for a, b in zip(seen, seen[1:]) if b.startswith("jump_air") and not a.startswith("jump_air"))
        assert leaps >= 2, seed
        for (a, _ax), (b, cat_x) in zip(trace, trace[1:]):
            if a.animation.startswith("jump_air") and b.animation.startswith("jump_land") and b.ball is not None:
                assert abs(b.ball.x - cat_x) >= 60, seed  # elle a filé
        assert pet.scene is None and pet.ball is None, seed  # partie hors de l'écran


def test_the_frog_is_drawn_sitting_or_hopping_and_cannot_be_picked_up():
    pet, trace = game(3)
    frogs = [v.ball for v, _x in trace if v.ball is not None]
    assert frogs and {b.anim for b in frogs} <= {"frog_sit_left", "frog_sit_right", "frog_hop_left", "frog_hop_right"}
    assert all(b.visible and not b.grabbable for b in frogs)


def test_a_stray_frog_hops_off_when_the_game_is_interrupted():
    pet = settled_pet(1, 800)
    pet.request("frog")
    for _ in range(int(10 / DT)):
        pet.update(DT, SNAP)
        if pet.ball is not None:
            break
    assert pet.ball is not None and pet.ball.kind is FROG
    pet.grab(pet.body.x, pet.body.y - 30)
    pet.release()
    for _ in range(int(90 / DT)):
        pet.update(DT, SNAP)
        if pet.ball is None or pet.ball.kind is not FROG:
            break
    assert pet.ball is None or pet.ball.kind is not FROG  # partie (il peut ensuite sortir sa pelote)


def test_no_frog_without_the_extension():
    anims = {k: v for k, v in make_anims().items() if not k.startswith("frog_")}
    pet = settled_pet(1, 800, anims=anims)
    pet.request("frog")
    for _ in range(int(5 / DT)):
        pet.update(DT, SNAP)
    assert pet.ball is None and pet.scene is None


def test_a_hopping_frog_moves_with_its_window():
    def snap(x):
        return WorldSnapshot(monitors=(SCREEN,), windows=(WinRect(1, Rect(x, 600, 800, 300)),), cursor=None)

    frog = Frog(700, 600, heading=1)
    frog.update(DT, snap(400), compute_surfaces(snap(400)))
    assert frog.grounded
    frog.hop(1)
    for i in range(int(0.8 / DT)):
        s = snap(400 if i < 3 else 500)  # la fenêtre glisse de 100 px pendant le saut
        frog.update(DT, s, compute_surfaces(s))
    assert abs(frog.x - (700 + 100 + FROG_HOP[-1])) < 1


def test_a_leaving_frog_goes_off_its_screen_without_jumping_to_the_other_one():
    tall = Monitor(Rect(0, 0, 1024, 1024), Rect(0, 0, 1024, 1024))
    short = Monitor(Rect(1024, 0, 1280, 720), Rect(1024, 0, 1280, 720))
    snap = WorldSnapshot(monitors=(tall, short), windows=(), cursor=None)
    segs = compute_surfaces(snap)
    frog = Frog(900, 1024, heading=1)
    frog.update(DT, snap, segs)
    frog.leave()
    ys = []
    for _ in range(int(10 / DT)):
        frog.update(DT, snap, segs)
        ys.append(frog.y)
        if frog.gone:
            break
    assert frog.gone and min(ys) >= 1023


def test_the_frog_hops_in_from_off_screen():
    for seed, x in ((0, 1500), (1, 300)):
        _pet, trace = game(seed, x)
        first = next(v.ball for v, _x in trace if v.ball is not None)
        assert first.x > 1920 if x > 960 else first.x < 0, seed


def test_a_frog_moves_only_while_its_legs_are_off_the_ground():
    segs = compute_surfaces(SNAP)
    frog = Frog(1000, 1080, heading=1)
    frog.update(DT, SNAP, segs)
    frog.hop(1)
    seen = {}
    for _ in range(int(0.7 / DT)):
        frog.update(DT, SNAP, segs)
        if frog.hopping:
            seen.setdefault(frog.frame, set()).add(frog.x)
    assert seen[2] == seen[3] == seen[4] == {1000 + FROG_HOP[-1]}  # posée : elle ne glisse plus (DLL : ±30 px en l'air)


def test_the_frog_hops_the_same_way_both_ways():
    import json
    from tests.anim_helpers import MANIFEST
    spec = json.loads((MANIFEST.parent / "extensions" / "fun.json").read_text(encoding="utf-8"))["animations"]
    width = 208 // 2  # cellule de 509/510 (2 colonnes)
    assert spec["frog_hop_right"]["anchor"][0] == width - spec["frog_hop_left"]["anchor"][0]
