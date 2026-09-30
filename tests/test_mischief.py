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
    # la télé s'allume, joue puis s'éteint DERRIÈRE le chat assis de dos (images en couches)
    assert names.index("tv_on") < names.index("tv_watch") < names.index("tv_off") < names.index("tv_leave")
    assert "tv_power" not in names and "tv_on_air" not in names


def test_fishbowl_scene():
    snap = world()
    pet = settled_pet(snap)
    pet.request("fishbowl")
    names, _ = run(pet, snap, 15)
    assert "fishbowl" in names


def test_mischief_happens_on_its_own():
    snap = world(WinRect(9, Rect(500, 250, 900, 600)))
    seen = set()
    for seed in range(3):
        pet = settled_pet(snap, seed)
        names, _ = run(pet, snap, 240)
        seen.update(n for n in names if n in ("paw_prints", "fishbowl", "climb", "tv_watch", "yarn_pat"))
    assert len(seen) >= 2


def test_cat_walks_under_a_high_window_before_climbing_it():
    snap = world(WinRect(9, Rect(900, 250, 600, 600)))
    pet = settled_pet(snap, seed=2)
    pet.body.x = 200  # loin de la fenêtre
    pet.request("climb")
    names, _ = run(pet, snap, 40)
    assert "climb" in names
    assert pet.body.support is not None and pet.body.support.owner == 9


def test_closing_the_window_during_the_climb_makes_the_cat_fall():
    high = WinRect(9, Rect(500, 250, 900, 600))
    snap = world(high)
    pet = settled_pet(snap, seed=1)
    pet.body.x = 900
    pet.request("climb")
    names, events = [], []
    for _ in range(int(20 / DT)):
        view = pet.update(DT, snap)
        names.append(view.animation)
        events.extend(view.events)
        if view.animation == "climb":
            break
    for _ in range(15):  # grimpe un peu…
        pet.update(DT, snap)
    empty = world()  # …et la fenêtre se ferme
    after, events = run(pet, empty, 5)
    assert "climb_top" not in after
    assert not [e for e in events if isinstance(e, tuple) and e[0] == "claws"]
    assert pet.body.grounded and pet.body.y == 1080


def test_a_window_moved_during_the_climb_is_followed():
    snap = world(WinRect(9, Rect(500, 250, 900, 600)))
    pet = settled_pet(snap, seed=1)
    pet.body.x = 900
    pet.request("climb")
    for _ in range(int(20 / DT)):
        if pet.update(DT, snap).animation == "climb":
            break
    moved = world(WinRect(9, Rect(500, 400, 900, 600)))  # le haut descend de 150 px
    landed = False
    for _ in range(int(20 / DT)):
        view = pet.update(DT, moved)
        s = pet.body.support
        landed |= s is not None and s.owner == 9 and pet.body.y == 400 and view.animation.startswith("sit_back")
    assert landed


def test_the_cat_goes_out_through_its_flap_and_comes_back():
    snap = world()
    pet = settled_pet(snap)
    pet.request("outing")
    views = []
    for _ in range(int(400 / DT)):
        views.append(pet.update(DT, snap))
    names = [v.animation for v in views]
    first_exit = names.index("exit_flap")
    back = names.index("enter_flap", first_exit)
    hidden = [v.hidden for v in views[first_exit:back]]
    assert sum(hidden) * DT > 30  # absent un bon moment
    assert not views[-1].hidden or pet.away


def test_a_request_brings_the_cat_back_early():
    snap = world()
    pet = settled_pet(snap)
    pet.request("outing")
    for _ in range(int(10 / DT)):
        if pet.update(DT, snap).hidden:
            break
    assert pet.away
    pet.request("feed")
    names, _ = run(pet, snap, 6)
    assert "enter_flap" in names and "cupboard_enter" in names
