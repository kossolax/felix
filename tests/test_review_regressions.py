"""Défauts trouvés à la relecture des corrections des mini-jeux (chacun reproduit avant d'être corrigé)."""
import random

from felix.core.actions import Chase, Play
from felix.core.ball import Ball
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
ANIMS = make_anims()


def snap(windows=(), cursor=None, monitors=(SCREEN,)):
    return WorldSnapshot(monitors=monitors, windows=windows, cursor=cursor)


def settled(seed=5, world=None, needs=None):
    world = world or snap()
    pet = Pet(ANIMS, rng=random.Random(seed), needs=needs or Needs(0.8, 0.8))
    for _ in range(int(3 / DT)):
        pet.update(DT, world)
    while pet.scene is not None:
        pet.update(DT, world)
    return pet


def run(pet, seconds, world=None, until=None):
    world = world or snap()
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, world)
        if until is not None and until(pet, view):
            return view
    return None


def test_a_treat_just_out_of_reach_does_not_freeze_the_app():
    from felix.core.feeding import TREAT
    w1, w2 = WinRect(1, Rect(300, 700, 400, 380)), WinRect(2, Rect(1000, 700, 400, 380))
    world = snap(windows=(w1, w2))
    pet = settled(1, world, Needs(0.9, 0.9))
    pet.still = True
    segs = compute_surfaces(world)
    seg = next(s for s in segs if s.owner == 1)
    pet.mode = "script"
    pet.body.x, pet.body.y, pet.body.support, pet.body.owner_rect = 669.5, seg.y, seg, w1.rect
    pet.update(DT, world)
    pet.body.x = 669.5
    treat = Ball(1206, 600, kind=TREAT)  # sur la 2e fenêtre : à 500 px de la place la plus proche, 500,5 de lui
    treat.taken = False
    for _ in range(30):
        treat.update(DT, world, segs)
    assert treat.grounded
    pet.treats = [treat]
    calls = []
    real = pet._eat_treat

    def counting(t):
        calls.append(t)
        if len(calls) > 50:
            raise RuntimeError("_do_treats tourne sans fin sans rien produire : l'appli se fige")
        return real(t)

    pet._eat_treat = counting
    next(pet._do_treats(), None)  # rend la main : une action, ou la fin de la scène


def test_food_held_out_while_he_finishes_the_treats_is_not_lost():
    pet = settled(2)
    pet.hold_item("treats")
    run(pet, 0.5)
    pet.drop_treat(pet.body.x + 400, 800)
    pet.stop_holding()
    pet.grab(pet.body.x, pet.body.y - 30)
    pet.release()
    run(pet, 1.5, until=lambda p, _v: p.scene == "treats")
    pet.hold_item("can")  # pendant qu'il reprend ses friandises
    view = run(pet, 90, until=lambda p, _v: p.player.animation.name in ("can_sit", "can_wag"))
    assert view is not None and pet.holding == "can"
    assert pet.serve()


def test_changing_ones_mind_twice_about_the_kitten_shows_it():
    pet = settled(5)
    pet.show_kitten()
    run(pet, 5, until=lambda _p, v: v.animation == "sit_front")
    pet.hide_kitten()
    pet.grab(pet.body.x, pet.body.y - 30)  # la scène est coupée avant qu'il arrive
    pet.release()
    run(pet, 3)
    pet.show_kitten()
    assert pet.kitten_coming
    run(pet, 40, until=lambda p, _v: p.kitten is not None)
    assert pet.kitten is not None and not pet.kitten.leaving


def test_the_same_menu_choice_twice_is_played_once():
    pet = settled(3)
    pet.request("bin")
    run(pet, 1)
    assert pet.scene == "bin"
    for _ in range(3):
        pet.request("tv")
    pet.request("bin")
    assert pet._requests == ["tv"]


def test_a_treat_the_cat_was_about_to_eat_shows_again_if_he_is_picked_up():
    pet = settled(4)
    pet.hold_item("treats")
    run(pet, 0.5)
    pet.drop_treat(pet.body.x + 200, 800)
    pet.stop_holding()
    run(pet, 10, until=lambda p, _v: p.player.animation.name.startswith("treats_crouch_"))
    pet._run(iter([Play("stand_right", duration=60)]))  # interrompu (comme attrapé) pendant qu'il se baisse
    assert pet.treats and not pet.treats[0].taken


def test_the_kitten_felix_draws_falls_with_him_when_his_window_closes():
    w = WinRect(1, Rect(300, 600, 900, 480))
    world, empty = snap(windows=(w,)), snap()
    for seed in range(20):
        pet = settled(seed, world)
        seg = next(s for s in compute_surfaces(world) if s.owner == 1)
        pet.body.x, pet.body.y, pet.body.support, pet.body.owner_rect = 700, seg.y, seg, w.rect
        pet._requests.clear()
        pet._run(pet._brain())
        pet.show_kitten()
        if run(pet, 30, world, until=lambda p, _v: p.player.animation.name.startswith("kitten_milk_")) is None:
            continue  # sans le lait cette fois
        assert pet.kitten is None  # encore dessiné par les images de Felix
        run(pet, 8, empty)  # la fenêtre se ferme : ils tombent
        assert pet.kitten is not None and pet.kitten.visible and pet.kitten.support is not None
        return
    raise AssertionError("jamais de lait")


def test_leaving_paw_prints_is_not_sitting():
    pet = settled(6)
    pet._run(iter([Play("paw_prints"), Play("stand_right", duration=60)]))
    run(pet, 0.3)
    assert pet.player.animation.name == "paw_prints"
    pet.hold_item("can")
    seen = []
    run(pet, 5, until=lambda p, v: seen.append(v.animation) or v.animation == "can_sit")
    assert "sit_down" in seen


def test_chasing_from_beyond_the_margin_does_not_jump():
    pet = settled(7)
    pet.ball = Ball(1500, 1080)
    pet.ball.update(DT, snap(), compute_surfaces(snap()))
    pet.ball.vx = -200.0
    pet.body.x, pet.facing = 1915, "left"
    pet.mode = "script"
    pet._run(iter([Chase(1), Play("stand_left", duration=60)]))
    xs = [pet.body.x]
    for _ in range(30):
        pet.update(DT, snap())
        xs.append(pet.body.x)
    assert max(abs(b - a) for a, b in zip(xs, xs[1:])) <= 13


def test_on_two_screens_with_different_floors_the_mouse_does_not_float_nor_vanish_midway():
    left = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))  # barre des tâches
    right = Monitor(Rect(1920, 0, 1920, 1080), Rect(1920, 0, 1920, 1080))
    world = snap(monitors=(left, right))
    pet = settled(3, world)
    floor = next(s for s in compute_surfaces(world) if s.y == 1040)
    pet.body.x, pet.body.y, pet.body.support = 1500, 1040, floor
    pet._requests.clear()
    pet._run(pet._brain())
    pet.request("mouse")
    mice = []
    for _ in range(int(60 / DT)):
        pet.update(DT, world)
        if pet.ball is not None and pet.ball.kind.anim.startswith("mouse"):
            mice.append((pet.ball.x, pet.ball.y))
    assert mice and not (mice[0][0] > 1920 and mice[0][1] == 1040)  # pas en l'air au-dessus du 2e écran
