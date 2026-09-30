import random

from felix.core.needs import Needs
from felix.core.pet import JUMP_UP, Pet
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))


def world(*windows):
    return WorldSnapshot(monitors=(SCREEN,), windows=tuple(windows), cursor=None)


def settled_pet(snap, seed=5):
    pet = Pet(make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, snap)
    return pet


def run(pet, snap, seconds):
    names, events = [], []
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, snap)
        names.append(view.animation)
        events.extend(view.events)
    return names, events


def test_paw_prints_leave_marks_on_the_screen():
    snap = world()
    pet = settled_pet(snap)
    pet.request("prints")
    names, events = run(pet, snap, 15)
    assert "paw_prints" in names
    marks = [e for e in events if isinstance(e, tuple) and e[0] == "marks"]
    assert marks and len(marks[0][1]) == 2  # (il peut recommencer de lui-même)
    (sheet_rect, (x, y)), _ = marks[0][1]
    assert sheet_rect[0] == 122 and sheet_rect[3:] == (9, 12)  # (planche, x, y, l, h)
    assert 0 <= x < 1920 and 800 < y < 1080  # au-dessus du sol, près du chat


def test_cat_climbs_a_window_too_high_to_jump_and_leaves_claw_marks():
    high = WinRect(9, Rect(500, 250, 900, 600))  # haut à 830 px du sol
    assert 1080 - 250 > JUMP_UP
    snap = world(high)
    pet = settled_pet(snap, seed=1)
    pet.body.x = 900
    pet.request("climb")
    names, events = run(pet, snap, 30)
    assert names.index("climb_leap") < names.index("climb") < names.index("climb_top")
    assert pet.body.support is not None and pet.body.support.owner == 9
    claws = [e for e in events if isinstance(e, tuple) and e[0] == "claws"]
    assert claws and claws[0][2] < claws[0][3]  # du haut vers le bas


def test_tv_scene():
    snap = world()
    pet = settled_pet(snap)
    pet.request("tv")
    names, _ = run(pet, snap, 40)
    assert names.index("tv_power") < names.index("tv_on_air") < names.index("tv_leave")


def test_fishbowl_scene():
    snap = world()
    pet = settled_pet(snap)
    pet.request("fishbowl")
    names, _ = run(pet, snap, 15)
    assert "fishbowl" in names


def test_yarn_scene_plays_in_order_and_needs_room():
    snap = world()
    pet = settled_pet(snap)
    pet.body.x = 1880  # collé au bord droit : la pelote roule vers la droite
    pet.request("yarn")
    names, _ = run(pet, snap, 40)
    order = ["yarn_roll_in", "yarn_play", "yarn_unroll", "yarn_follow", "yarn_bat_away"]
    assert [names.index(n) for n in order] == sorted(names.index(n) for n in order)
    assert pet.body.grounded


def test_mischief_happens_on_its_own():
    snap = world(WinRect(9, Rect(500, 250, 900, 600)))
    seen = set()
    for seed in range(3):
        pet = settled_pet(snap, seed)
        names, _ = run(pet, snap, 240)
        seen.update(n for n in names if n in ("paw_prints", "fishbowl", "climb", "tv_on_air", "yarn_play"))
    assert len(seen) >= 2


def test_cat_walks_under_a_high_window_before_climbing_it():
    snap = world(WinRect(9, Rect(900, 250, 600, 600)))
    pet = settled_pet(snap, seed=2)
    pet.body.x = 200  # loin de la fenêtre
    pet.request("climb")
    names, _ = run(pet, snap, 40)
    assert "climb" in names
    assert pet.body.support is not None and pet.body.support.owner == 9
