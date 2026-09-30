import random

from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.world import Monitor, Rect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
WORLD = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)


def settled_pet(seed=3, needs=None):
    pet = Pet(make_anims(), rng=random.Random(seed), needs=needs)
    for _ in range(int(4 / DT)):
        pet.update(DT, WORLD)
    return pet


def run(pet, seconds):
    names, events = [], []
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, WORLD)
        names.append(view.animation)
        events.extend(view.events)
    return names, events


def test_feeding_plays_the_cupboard_scene_and_satisfies_hunger():
    pet = settled_pet(needs=Needs(hunger=0.9, thirst=0.1))
    pet.request("feed")
    names, events = run(pet, 40)
    assert names.index("cupboard_enter") < names.index("cupboard_exit") < names.index("cupboard_leave")
    assert pet.needs.hunger < 0.05
    assert "crunch" in events


def test_milk_scene_satisfies_thirst():
    pet = settled_pet(needs=Needs(hunger=0.1, thirst=0.9))
    pet.request("drink")
    names, events = run(pet, 40)
    for scene in ("milk_arrive", "milk_spill", "milk_drink"):
        assert scene in names
    assert pet.needs.thirst < 0.05
    assert "lap" in events


def test_scene_needs_room_so_the_cat_first_moves_away_from_the_edge():
    pet = settled_pet()
    seg = pet.body.support
    pet.body.x = seg.x1 - 40  # collé au bord droit
    pet.request("feed")
    xs = []
    for _ in range(int(20 / DT)):
        view = pet.update(DT, WORLD)
        if view.animation == "cupboard_enter":
            xs.append(pet.body.x)
    assert xs and max(xs) <= seg.x1 - 100


def test_a_hungry_cat_meows_for_food():
    pet = settled_pet(needs=Needs(hunger=0.95, thirst=0.1))
    _, events = run(pet, 90)
    assert "meow" in events


def test_needs_grow_while_the_pet_lives():
    pet = settled_pet(needs=Needs(hunger=0.0, thirst=0.0))
    run(pet, 60)
    assert pet.needs.hunger > 0


def test_a_second_request_waits_for_the_current_scene():
    pet = settled_pet(needs=Needs(hunger=0.9, thirst=0.9))
    pet.request("feed")
    pet.request("drink")
    names, _ = run(pet, 80)
    assert names.index("cupboard_leave") < names.index("milk_arrive")
    assert pet.needs.hunger < 0.05 and pet.needs.thirst < 0.05


def test_stroking_the_cat_makes_it_sit_and_purr():
    pet = settled_pet()
    pet.stroke()
    names, events = run(pet, 6)
    assert "purr" in events
    assert "sit_front" in names
