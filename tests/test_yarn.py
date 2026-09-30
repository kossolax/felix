"""Partie de pelote : une vraie pelote qui roule, que le chat guette, rattrape, tapote et renvoie."""
import random

from felix.core.ball import Ball
from felix.core.needs import Needs
from felix.core.pet import BALL_AT_FEET, BALL_CATCH, BAT_FROM, Pet
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
DRAWN = {"yarn_sniff", "yarn_pat", "yarn_unroll", "yarn_follow", "yarn_bat_away"}


def world(*windows):
    return WorldSnapshot(monitors=(SCREEN,), windows=tuple(windows), cursor=None)


def settled_pet(snap, seed=5, x=None):
    pet = Pet(make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, snap)
    if x is not None:
        pet.body.x = x
    return pet


def lay_ball(pet, snap, x, y=1080):
    pet.ball = Ball(x, y)
    pet.ball.update(DT, snap, compute_surfaces(snap))
    assert pet.ball.resting


def run(pet, snap, seconds, until=None):
    """[(vue, x du chat, x de la pelote ou None)] image par image."""
    out = []
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, snap)
        out.append((view, pet.body.x, pet.ball.x if pet.ball else None))
        if until is not None and until(pet, view):
            break
    return out


def names(trace):
    return [v.animation for v, _cx, _bx in trace]


def test_the_menu_game_has_several_rounds_and_ends_with_the_ball_gone():
    snap = world()
    for seed in range(4):
        pet = settled_pet(snap, seed, x=700)
        pet.request("yarn")
        trace = run(pet, snap, 150, until=lambda p, _v: p.scene is None)
        seen = names(trace)
        assert pet.scene is None and pet.ball is None, seed
        assert any(v.ball is not None for v, _c, _b in trace)
        starts = [i for i, (a, b) in enumerate(zip(seen, seen[1:])) if b != a]
        bats = sum(1 for i in starts if seen[i + 1] == "yarn_bat")
        assert bats >= 2, (seed, bats)


def test_the_ball_arrives_rolling_from_the_edge_or_dangling_on_its_string():
    snap = world()
    openings = set()
    for seed in range(8):
        pet = settled_pet(snap, seed, x=900)
        pet.request("yarn")
        trace = run(pet, snap, 6)
        first = next(v.ball for v, _c, _b in trace if v.ball is not None)
        if "string_leap" in names(trace):
            openings.add("ficelle")
        elif first.x < 60 or first.x > 1860:
            openings.add("bord")
    assert openings == {"ficelle", "bord"}


def test_the_real_ball_hides_while_the_cat_plays_with_the_drawn_one():
    snap = world()
    pet = settled_pet(snap, 2, x=700)
    pet.request("yarn")
    trace = run(pet, snap, 150, until=lambda p, _v: p.scene is None)
    drawn = [v for v, _c, _b in trace if v.animation in DRAWN]
    assert drawn and all(v.ball is None or not v.ball.visible for v in drawn)
    moving = [v for v, _c, _b in trace if v.animation.startswith(("walk_", "trot_", "stand_", "jump_air")) and v.ball]
    assert moving and all(v.ball.visible for v in moving)


def test_the_ball_lies_exactly_where_the_drawn_one_is():
    snap = world()
    checked = 0
    for seed in range(3):
        pet = settled_pet(snap, seed, x=700)
        pet.request("yarn")
        trace = run(pet, snap, 150, until=lambda p, _v: p.scene is None)
        for (prev, _pc, _pb), (view, cat_x, ball_x) in zip(trace, trace[1:]):
            side = -1 if view.mirrored else 1
            if view.animation in ("yarn_sniff", "yarn_pat") and prev.animation == "sit_down":
                assert ball_x == cat_x + side * BALL_AT_FEET
                checked += 1
            if view.animation == "yarn_bat" and view.ball and prev.ball and view.ball.visible and not prev.ball.visible:
                assert abs(ball_x - (cat_x + side * BAT_FROM)) < 20  # repart de sous la patte
                checked += 1
    assert checked >= 4


def test_a_bat_sends_the_ball_rolling_and_the_cat_goes_after_it():
    snap = world()
    pet = settled_pet(snap, 1, x=700)
    pet.request("yarn")
    trace = run(pet, snap, 150, until=lambda p, _v: p.scene is None)
    seen = names(trace)
    first_bat = seen.index("yarn_bat")
    end_bat = next(i for i in range(first_bat, len(seen)) if seen[i] != "yarn_bat")
    ball_then = trace[end_bat][2]
    later = [bx for _v, _c, bx in trace[end_bat:end_bat + 90] if bx is not None]
    assert max(abs(bx - ball_then) for bx in later) > 40  # elle roule
    assert any(n.startswith(("trot_", "jump_")) for n in seen[end_bat:])  # il la suit
    assert seen.count("sit_down") >= 2  # et rejoue


def test_the_cat_pounces_on_a_ball_lying_a_little_way_off():
    snap = world()
    pounced = 0
    for seed in range(6):
        pet = settled_pet(snap, seed, x=800)
        lay_ball(pet, snap, 1100)
        pet.request("yarn")
        trace = run(pet, snap, 12, until=lambda p, v: v.animation == "sit_down")
        seen = names(trace)
        if "stalk_right" in seen:
            assert seen.index("stalk_right") < seen.index("leap_prep_right") < seen.index("jump_air_right")
            pounced += 1
        assert abs(pet.body.x - (1100 - BALL_AT_FEET)) <= BALL_CATCH
    assert pounced >= 2


def test_the_cat_does_not_pounce_on_a_ball_right_in_front_of_him():
    snap = world()
    for seed in range(8):
        pet = settled_pet(snap, seed, x=800)
        lay_ball(pet, snap, 950)  # un bond de 110 px : il resterait presque sur place, corps étiré
        pet.request("yarn")
        seen = names(run(pet, snap, 12, until=lambda p, v: v.animation == "sit_down"))
        assert "leap_prep_right" not in seen, seed
        assert abs(pet.body.x - (950 - BALL_AT_FEET)) <= BALL_CATCH


def test_throwing_the_ball_makes_the_cat_run_after_it():
    snap = world()
    pet = settled_pet(snap, 3, x=400)
    lay_ball(pet, snap, 450)
    pet.grab_ball()
    pet.drag_ball(500, 700)
    pet.throw_ball(900, -300)
    assert pet.scene == "yarn" or "yarn" in pet._requests
    trace = run(pet, snap, 30, until=lambda p, v: v.animation == "yarn_bat")
    assert names(trace)[-1] == "yarn_bat" and pet.body.x > 1000


def test_a_still_cat_ignores_a_thrown_ball():
    snap = world()
    pet = settled_pet(snap, 3, x=400)
    pet.still = True
    lay_ball(pet, snap, 450)
    pet.grab_ball()
    pet.throw_ball(900, -300)
    run(pet, snap, 5)
    assert pet.scene is None and "yarn" not in pet._requests


def test_the_cat_jumps_onto_a_window_to_fetch_the_ball():
    snap = world(WinRect(1, Rect(900, 700, 600, 380)))
    pet = settled_pet(snap, 4, x=500)
    lay_ball(pet, snap, 1200, 700)
    pet.request("yarn")
    run(pet, snap, 25, until=lambda p, v: v.animation in ("yarn_sniff", "yarn_pat", "yarn_bat"))
    assert pet.body.support.owner == 1 and abs(pet.ball.x - pet.body.x) == BALL_AT_FEET


def test_a_ball_out_of_reach_makes_the_cat_give_up_and_stays_there():
    snap = world(WinRect(1, Rect(700, 150, 800, 930)))  # 930 px au-dessus du sol : trop haut
    pet = settled_pet(snap, 4, x=500)
    lay_ball(pet, snap, 1100, 150)
    pet.request("yarn")
    run(pet, snap, 20, until=lambda p, _v: p.scene is None)
    assert pet.scene is None and pet.ball is not None and pet.ball.support.owner == 1


def test_holding_the_ball_too_long_makes_the_cat_give_up():
    snap = world()
    pet = settled_pet(snap, 4, x=500)
    lay_ball(pet, snap, 900)
    pet.request("yarn")
    run(pet, snap, 1)
    pet.grab_ball()
    pet.drag_ball(900, 500)
    run(pet, snap, 30, until=lambda p, _v: p.scene is None)
    assert pet.scene is None and pet.ball.held


def test_a_ball_lying_around_tempts_the_cat():
    snap = world()
    played = False
    for seed in range(3):
        pet = settled_pet(snap, seed, x=400)
        lay_ball(pet, snap, 1200)
        trace = run(pet, snap, 150, until=lambda _p, v: v.animation == "yarn_bat")
        played |= names(trace)[-1] == "yarn_bat"
    assert played


def test_a_ball_from_the_toybox_hops_out_toward_the_cat():
    snap = world()
    pet = settled_pet(snap, 4, x=600)
    pet.toss_ball(1200, 1000, home="box")
    assert pet.ball.home == "box" and pet.ball.vx < 0 and pet.ball.vy < 0
    assert pet.scene == "yarn"


def test_putting_the_ball_away_ends_the_game():
    snap = world()
    pet = settled_pet(snap, 4, x=600)
    pet.request("yarn")
    run(pet, snap, 8)
    pet.put_ball_away()
    run(pet, snap, 10, until=lambda p, _v: p.scene is None)
    assert pet.scene is None and pet.ball is None


def test_grabbing_the_cat_mid_game_shows_the_ball_again():
    snap = world()
    pet = settled_pet(snap, 2, x=700)
    pet.request("yarn")
    run(pet, snap, 60, until=lambda _p, v: v.animation in ("yarn_sniff", "yarn_pat"))
    pet.grab(pet.body.x, pet.body.y - 30)
    view = pet.update(DT, snap)
    assert view.ball is not None and view.ball.visible
