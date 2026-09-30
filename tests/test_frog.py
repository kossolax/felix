"""Extension Fun and Games : la grenouille. Elle arrive en sautant ; le chat la guette et bondit,
elle lui échappe d'un saut à chaque fois, puis s'en va."""
import random

from felix.core.frog import FROG, Frog
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.surfaces import compute_surfaces
from felix.core.tuning import FROG_HOP
from felix.core.world import Monitor, Rect, WorldSnapshot
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
