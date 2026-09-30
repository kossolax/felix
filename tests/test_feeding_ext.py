"""Extension Feeding : pâtée, lait et friandises Felix, tenus au bout du curseur.

L'appli montre l'objet sous le curseur ; le chat attend, assis (et remue la queue quand le
curseur approche) ; un clic gauche sert, un clic droit annule. Les friandises tombent là où on
clique, et le chat va les manger une à une."""
import random

from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.tuning import HOLD_PATIENCE
from felix.core.world import Monitor, Rect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))


def snap(cursor=None):
    return WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=cursor)


def settled_pet(seed=5, x=900, needs=None, anims=None):
    pet = Pet(anims or make_anims(), rng=random.Random(seed), needs=needs or Needs(0.8, 0.8))
    for _ in range(int(4 / DT)):
        pet.update(DT, snap())
    pet.body.x = x
    return pet


def run(pet, seconds, cursor=None, until=None):
    out = []
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, snap(cursor))
        out.append(view)
        if until is not None and until(pet, view):
            break
    return out


def names(views):
    return [v.animation for v in views]


def in_order(seen, order):
    return all(n in seen for n in order) and [seen.index(n) for n in order] == sorted(seen.index(n) for n in order)


def test_the_cat_waits_for_the_can_then_eats_when_served():
    pet = settled_pet()
    pet.hold_item("can")
    waiting = names(run(pet, 6, cursor=(1500, 300)))
    assert pet.holding == "can" and "can_sit" in waiting and "can_serve" not in waiting
    pet.serve()
    seen = names(run(pet, 40, until=lambda p, _v: p.scene is None))
    assert in_order(seen, ["can_serve", "can_eat", "can_eat_last", "can_done", "can_rise"])
    assert pet.holding is None and pet.needs.hunger < 0.05


def test_the_cat_wags_its_tail_when_the_can_comes_near():
    pet = settled_pet()
    pet.hold_item("can")
    far = names(run(pet, 5, cursor=(1600, 300)))
    near = names(run(pet, 3, cursor=(pet.body.x + 60, pet.body.y - 60)))
    assert "can_wag" not in far and "can_wait_wag" not in far
    assert "can_wag" in near


def test_the_can_can_be_taken_away():
    pet = settled_pet()
    pet.hold_item("can")
    run(pet, 4)
    pet.stop_holding()
    seen = names(run(pet, 10, until=lambda p, _v: p.scene is None))
    assert "can_serve" not in seen and "sit_up" in seen
    assert pet.holding is None and pet.needs.hunger > 0.5


def test_milk_is_poured_into_the_bowl_when_served():
    pet = settled_pet()
    pet.hold_item("carton")
    waiting = names(run(pet, 6))
    assert "carton_bowl_in" in waiting and "carton_pour" not in waiting
    pet.serve()
    seen = names(run(pet, 40, until=lambda p, _v: p.scene is None))
    assert in_order(seen, ["carton_pour", "carton_look", "carton_lap", "carton_lap_last", "carton_lick",
                           "carton_clear"])
    assert pet.needs.thirst < 0.05


def test_taking_the_milk_away_clears_the_bowl():
    pet = settled_pet()
    pet.hold_item("carton")
    run(pet, 5)
    pet.stop_holding()
    seen = names(run(pet, 10, until=lambda p, _v: p.scene is None))
    assert "carton_bowl_out" in seen and "carton_pour" not in seen


def test_the_cat_fetches_each_treat_where_it_fell_and_eats_it():
    pet = settled_pet(x=900)
    pet.hold_item("treats")
    run(pet, 2)
    for x in (1300, 600, 1100):
        pet.drop_treat(x, 500)
        run(pet, 0.5)
    pet.stop_holding()
    views = run(pet, 90, until=lambda p, _v: p.scene is None)
    seen = names(views)
    eats = sum(1 for a, b in zip(seen, seen[1:]) if b.startswith("treats_eat_") and not a.startswith("treats_eat_"))
    assert eats == 3 and "treats_eat_left" in seen and "treats_eat_right" in seen
    assert pet.treats == [] and pet.scene is None and pet.needs.hunger < 0.8


def test_a_treat_falls_to_the_floor_and_hides_once_the_cat_has_it():
    pet = settled_pet(x=900)
    pet.hold_item("treats")
    run(pet, 1)
    pet.drop_treat(1200, 400)
    fall = run(pet, 3)
    assert fall[-1].treats and fall[-1].treats[0].y == 1080 and fall[-1].treats[0].visible
    pet.stop_holding()
    for view in run(pet, 60, until=lambda p, _v: p.scene is None):
        if view.animation.startswith(("treats_crouch_", "treats_eat_")):
            assert all(not t.visible for t in view.treats)


def test_holding_nothing_too_long_gives_up():
    pet = settled_pet()
    pet.hold_item("can")
    run(pet, HOLD_PATIENCE + 10, until=lambda p, _v: p.holding is None)
    assert pet.holding is None


def test_nothing_to_hold_without_the_extension():
    anims = {k: v for k, v in make_anims().items() if not k.startswith(("can_", "carton_", "treats_"))}
    pet = settled_pet(anims=anims)
    pet.hold_item("can")
    assert pet.holding is None
