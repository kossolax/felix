"""Au bord d'une fenêtre, le chat regarde en bas (FelixEdgeLeft/Right de l'original), puis saute ou recule."""
import random

from felix.core.needs import Needs
from felix.core.pet import EDGE_REACH, Pet
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
WINDOW = WinRect(1, Rect(600, 700, 600, 380))


def world(*windows):
    return WorldSnapshot(monitors=(SCREEN,), windows=tuple(windows), cursor=None)


def cat_on(snap, wid, x, seed):
    pet = Pet(make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, snap)
    seg = next(s for s in compute_surfaces(snap) if s.owner == wid and s.spans(x))
    win = next(w for w in snap.windows if w.id == wid)
    pet.body.x, pet.body.y, pet.body.support, pet.body.owner_rect = x, seg.y, seg, win.rect
    return pet


def run(pet, snap, seconds):
    return [(pet.update(DT, snap).animation, pet.body.x) for _ in range(int(seconds / DT))]


def run_scene(pet, snap, seconds=40):
    """[(animation, x du chat)] jusqu'à la fin de la scène demandée (après l'activité en cours)."""
    trace, started = [], False
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, snap)
        trace.append((view.animation, pet.body.x))
        started |= pet.scene == "edge"
        if started and pet.scene is None:
            break
    return trace


def test_the_cat_walks_to_the_edge_and_looks_down_over_it():
    snap = world(WINDOW)
    sides = set()
    for seed in range(6):
        pet = cat_on(snap, 1, 900, seed)
        pet.request("edge")
        trace = run_scene(pet, snap)
        peeks = {(n, x) for n, x in trace if n in ("edge_left", "edge_right")}
        assert len(peeks) == 1, (seed, peeks)
        (name, x), = peeks
        assert x == (1200 - EDGE_REACH if name == "edge_right" else 600 + EDGE_REACH)
        sides.add(name)
    assert sides == {"edge_left", "edge_right"}


def test_after_looking_down_the_cat_jumps_or_backs_off():
    snap = world(WINDOW)
    endings = set()
    for seed in range(10):
        pet = cat_on(snap, 1, 900, seed)
        pet.request("edge")
        names = [n for n, _x in run_scene(pet, snap)]
        if any(n.startswith("jump_air") for n in names):
            assert pet.body.support.owner is None  # retombé au sol, au pied de la fenêtre
            assert not 600 <= pet.body.x < 1200
            endings.add("saut")
        else:
            assert any(n.startswith("edge_") and n.endswith("_back") for n in names)
            assert pet.body.support.owner == 1
            endings.add("recul")
    assert endings == {"saut", "recul"}


def test_no_peeking_where_a_window_in_front_hides_the_edge():
    front = WinRect(2, Rect(1100, 400, 400, 680))  # cache le bout droit de la fenêtre 1
    snap = world(front, WINDOW)
    for seed in range(6):
        pet = cat_on(snap, 1, 800, seed)
        pet.request("edge")
        trace = run_scene(pet, snap)
        assert {n for n, _x in trace if n.startswith("edge_")} <= {"edge_left", "edge_left_back"}, seed


def test_nothing_to_peek_over_on_the_floor():
    snap = world()
    pet = Pet(make_anims(), rng=random.Random(1), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, snap)
    pet.request("edge")
    names = [n for n, _x in run(pet, snap, 3)]
    assert not any(n.startswith("edge_") for n in names)


def test_a_cat_on_a_window_peeks_over_its_edge_on_its_own():
    snap = world(WINDOW)
    seen = False
    for seed in range(4):
        pet = cat_on(snap, 1, 900, seed)
        names = [n for n, _x in run(pet, snap, 120)]
        seen |= "edge_left" in names or "edge_right" in names
    assert seen
