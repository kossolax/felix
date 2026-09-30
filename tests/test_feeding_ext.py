"""Extension Feeding : pâtée, lait et friandises Felix, tenus au bout du curseur.

L'appli montre l'objet sous le curseur ; le chat attend, assis (et remue la queue quand le
curseur approche) ; un clic gauche sert, un clic droit annule. Les friandises tombent là où on
clique, et le chat va les manger une à une."""
import random

from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.tuning import HOLD_PATIENCE
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
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


def watching_pet(seed=5, x=900):
    """Assis, il suit le curseur des yeux (c'est là qu'on ouvre le menu d'un clic droit)."""
    pet = settled_pet(seed, x)
    cursor = (x + 60, 1080 - 150)
    pet._run(pet._do_watch())
    run(pet, 1.5, cursor=cursor)
    assert pet.player.animation.name.startswith(("head_", "paw_", "sit_"))
    return pet, cursor


def test_a_seated_cat_waits_for_the_food_without_standing_up_first():
    for kind in ("can", "carton"):
        pet, cursor = watching_pet()
        pet.hold_item(kind)
        seen = names(run(pet, 3, cursor=cursor, until=lambda p, _v: p.player.animation.name.startswith(kind)))
        assert seen[-1].startswith(kind) and "sit_down" not in seen, kind


def test_after_the_milk_the_cat_turns_before_walking_off():
    pet = settled_pet(2)
    pet.hold_item("carton")
    run(pet, 4)
    pet.serve()
    seen = names(run(pet, 40, until=lambda p, _v: p.scene is None))
    after = seen[len(seen) - 1 - seen[::-1].index("carton_clear") + 1:]
    assert after and after[0].startswith("turn_to_")  # assis de trois quarts : il se tourne avant de repartir


def test_food_held_while_the_cat_is_busy_is_served_only_once_he_waits_for_it():
    pet = settled_pet(2)
    pet.request("tv")
    run(pet, 3)
    assert pet.scene == "tv"
    pet.hold_item("can")
    assert pet.holding == "can"
    assert not pet.serve()  # il regarde la télé : le clic ne sert à rien, la boîte reste au curseur
    assert pet.holding == "can"
    run(pet, 60, until=lambda p, _v: p.player.animation.name == "can_sit")
    assert pet.serve()


def test_taking_the_food_back_before_the_cat_comes_cancels_it():
    pet = settled_pet(2)
    pet.request("tv")
    run(pet, 3)
    pet.hold_item("carton")
    pet.stop_holding()
    assert pet.holding is None and "carton" not in pet._requests
    pet.hold_item("can")  # on peut en tenir un autre tout de suite
    assert pet.holding == "can"


def test_giving_up_waiting_puts_the_food_away_at_once():
    pet = settled_pet(3)
    pet.hold_item("carton")
    for view in run(pet, HOLD_PATIENCE + 10):
        if view.animation == "carton_bowl_out":
            assert pet.holding is None  # la brique quitte le curseur dès qu'il renonce
            return
    raise AssertionError("il n'a pas renoncé")


def test_the_tail_wags_when_the_food_comes_near_the_cat_not_only_its_head():
    pet = settled_pet(4)
    pet.hold_item("can")
    run(pet, 3, until=lambda p, _v: p.player.animation.name == "can_sit")
    x = pet.body.x
    seen = names(run(pet, 2, cursor=(x + 90, 1080 + 10)))  # à côté de ses pattes, loin de sa tête
    assert "can_wag" in seen


def test_treats_left_on_the_floor_are_still_eaten_after_an_interruption():
    pet = settled_pet(5, 900)
    pet.hold_item("treats")
    run(pet, 1)
    for dx in (300, -300):
        pet.drop_treat(900 + dx, 800)
    run(pet, 1.5)
    pet.grab(pet.body.x, pet.body.y - 30)
    pet.release()
    run(pet, 40, until=lambda p, _v: not p.treats and p.scene is None)
    assert not pet.treats and pet.needs.hunger < 0.8 - 0.25  # les deux, mangées


def test_a_treat_on_a_far_window_is_fetched_not_forgotten():
    win = WinRect(1, Rect(1300, 700, 500, 380))
    world = WorldSnapshot(monitors=(SCREEN,), windows=(win,), cursor=None)
    pet = Pet(make_anims(), rng=random.Random(1), needs=Needs(0.8, 0.8))
    for _ in range(int(4 / DT)):
        pet.update(DT, world)
    pet.body.x = 300
    pet.hold_item("treats")
    for _ in range(int(1 / DT)):
        pet.update(DT, world)
    pet.drop_treat(1600, 500)  # à 1300 px : il faut s'approcher avant de sauter
    for _ in range(int(40 / DT)):
        pet.update(DT, world)
    assert pet.needs.hunger < 0.8 - 0.1


def test_a_treat_on_a_window_that_closes_while_the_cat_turns_does_not_freeze_him():
    win = WinRect(1, Rect(200, 700, 500, 380))
    world = WorldSnapshot(monitors=(SCREEN,), windows=(win,), cursor=None)
    empty = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)
    pet = Pet(make_anims(), rng=random.Random(1), needs=Needs(0.8, 0.8))
    for _ in range(int(4 / DT)):
        pet.update(DT, world)
    pet.body.x, pet.facing = 900, "right"
    pet.hold_item("treats")
    for _ in range(int(1 / DT)):
        pet.update(DT, world)
    pet.drop_treat(450, 500)
    for _ in range(int(3 / DT)):
        pet.update(DT, world)
        if pet.player.animation.name.startswith("turn_to_"):
            break
    for _ in range(int(5 / DT)):
        pet.update(DT, empty)  # la fenêtre de la friandise se ferme pendant son demi-tour
    assert not pet.player.animation.name.startswith("turn_to_")
