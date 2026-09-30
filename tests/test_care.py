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
    order = ["cupboard_appear", "cupboard_enter", "cupboard_eat", "cupboard_peek", "cupboard_exit", "cupboard_leave"]
    assert [names.index(n) for n in order] == sorted(names.index(n) for n in order)
    assert pet.needs.hunger < 0.05
    assert "crunch" in events


def test_the_cat_eats_a_while_inside_the_cupboard_pushing_its_door():
    pet = settled_pet(needs=Needs(hunger=0.9, thirst=0.1))
    pet.request("feed")
    names, events = run(pet, 40)
    assert names.count("cupboard_eat") * DT >= 3.5
    assert events.count("crunch") >= 2


def test_the_whole_cupboard_stays_in_place_through_the_scene():
    """Placard d'origine (planche 305) : 3 portes, dont les images du chat n'en dessinent que 2 ;
    il reste au même endroit par rapport aux pieds du chat, et la porte animée (135) sur celle du milieu."""
    anims = make_anims()
    spots, doors = set(), set()
    for name in ("cupboard_appear", "cupboard_enter", "cupboard_eat", "cupboard_peek", "cupboard_exit",
                 "cupboard_leave"):
        for f in anims[name].frames:
            (sheet, _rect, (ox, oy)), = f.under
            assert sheet == 305
            spots.add((ox - f.anchor[0], oy - f.anchor[1]))
            for sheet, _rect, (dx, dy) in f.over:
                assert sheet == 135
                doors.add((dx - f.anchor[0], dy - f.anchor[1]))
    assert spots == {(-40, -115)}
    assert doors == {(-40 + 73, -115 - 9)}


def test_the_cupboard_fades_away_once_the_cat_is_out():
    pet = settled_pet(needs=Needs(hunger=0.9, thirst=0.1))
    pet.request("feed")
    cat_x = None
    for _ in range(int(40 / DT)):
        view = pet.update(DT, WORLD)
        if view.animation == "cupboard_leave":
            cat_x = pet.body.x
        ghosts = [e for e in view.events if isinstance(e, tuple) and e[0] == "ghost"]
        if ghosts:
            break
    (_kind, (sheet, *_rect), (x, y)), = ghosts
    assert view.animation != "cupboard_leave" and cat_x is not None
    assert sheet == 305 and (x, y) == (round(cat_x - 40), 1080 - 115)


def test_milk_scene_satisfies_thirst():
    pet = settled_pet(needs=Needs(hunger=0.1, thirst=0.9))
    pet.request("drink")
    names, events = run(pet, 40)
    for scene in ("milk_arrive", "milk_spill", "milk_drink", "milk_lap", "milk_done"):
        assert scene in names
    assert pet.needs.thirst < 0.05
    assert "lap" in events


def test_the_cat_laps_the_spilt_milk_for_a_while():
    for seed in range(3):
        pet = settled_pet(seed, needs=Needs(hunger=0.1, thirst=0.9))
        pet.request("drink")
        names, events = run(pet, 40)
        assert names.count("milk_lap") * DT >= 4.0, seed
        assert events.count("lap") >= 2


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
    assert names.index("sit_down") < names.index("stroked") < names.index("sit_up")


def test_being_stroked_does_not_look_like_just_sitting():
    """Yeux mi-clos puis menton levé (planche 115), pas la pose assise ordinaire (103) : sans le son,
    une caresse ne se confond plus avec le chat qui s'assoit de lui-même."""
    anims = make_anims()
    assert anims["stroked"].sheet != anims["sit_front"].sheet


def test_leaving_goes_out_through_the_cat_flap():
    pet = settled_pet()
    pet.leave()
    names, _ = run(pet, 5)
    assert "exit_flap" in names and pet.gone
