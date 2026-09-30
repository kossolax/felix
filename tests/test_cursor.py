import random

import pytest

from felix.core.pet import Pet, direction_to
from felix.core.world import Monitor, Rect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))


def world(cursor=None):
    return WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=cursor)


def settled_pet(seed=2):
    pet = Pet(make_anims(), rng=random.Random(seed))
    for _ in range(int(4 / DT)):
        pet.update(DT, world((5, 5)))
    return pet


def play_for(pet, seconds, cursor_fn):
    names = []
    for _ in range(int(seconds / DT)):
        pet.update(DT, world(cursor_fn(pet)))
        names.append(pet.player.animation.name)
    return names


@pytest.mark.parametrize("cursor, expected", [
    ((100, -200), "up"),
    ((-200, 0), "left"),
    ((200, -30), "right"),
    ((-150, 200), "bottom_left"),
    ((150, 200), "bottom_right"),
])
def test_direction_from_the_head_to_the_cursor(cursor, expected):
    assert direction_to(0, 0, *cursor) == expected


def test_cat_looks_at_a_nearby_cursor():
    pet = settled_pet()
    names = play_for(pet, 20, lambda p: (p.body.x + 160, p.body.y - 200))
    assert "head_up" in names or "head_right" in names


def test_cat_paws_at_a_cursor_right_next_to_its_head():
    pet = settled_pet()
    names = play_for(pet, 20, lambda p: (p.body.x + 40, p.body.y - 70))
    assert any(n.startswith("paw_") for n in names)


def test_cat_goes_back_to_its_life_when_the_cursor_leaves():
    pet = settled_pet()
    play_for(pet, 15, lambda p: (p.body.x + 150, p.body.y - 150))
    names = play_for(pet, 20, lambda p: (5, 5))
    assert not any(n.startswith("head_") for n in names[-200:])


def test_cat_hunts_a_cursor_resting_on_its_floor():
    pet = settled_pet()
    target = (pet.body.x + 500 if pet.body.x < 960 else pet.body.x - 500, 1075)
    start = abs(target[0] - pet.body.x)
    names = play_for(pet, 60, lambda p: target)
    assert "pounce" in names
    assert abs(target[0] - pet.body.x) < start


def test_a_cursor_that_stops_moving_becomes_boring():
    pet = settled_pet()
    spot = (pet.body.x + 150, pet.body.y - 150)
    names = play_for(pet, 40, lambda p: spot)
    assert any(n.startswith("head_") for n in names)
    assert not any(n.startswith(("head_", "paw_")) for n in names[-300:])


def test_a_moving_cursor_keeps_the_cat_interested():
    pet = settled_pet()
    clock = {"t": 0}

    def wiggle(p):
        clock["t"] += 1
        return (p.body.x + 150 + (clock["t"] // 15 % 2) * 20, p.body.y - 150)

    names = play_for(pet, 25, wiggle)
    assert any(n.startswith("head_") for n in names[-60:])
