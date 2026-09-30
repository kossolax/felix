"""Extension Fun and Games : le ballon de plage. Le chat le tapote et le renvoie, puis finit par
bondir dessus et le crever, et se couche sur le ballon dégonflé."""
import random

from felix.core.ball import BEACH, Ball
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.surfaces import compute_surfaces
from felix.core.tuning import BEACH_LAUNCH
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
SNAP = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)
DRAWN = {"beach_sit", "beach_pounce", "beach_flat", "beach_flat_look", "beach_flat_fade", "beach_getup"}


def settled_pet(seed=5, x=None, anims=None):
    pet = Pet(anims or make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, SNAP)
    if x is not None:
        pet.body.x = x
    return pet


def run(pet, seconds, until=None):
    out = []
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, SNAP)
        out.append((view, pet.body.x, pet.player.index))
        if until is not None and until(pet, view):
            break
    return out


def names(trace):
    return [v.animation for v, _x, _i in trace]


def game(seed, x=800):
    pet = settled_pet(seed, x)
    pet.request("beachball")
    return pet, run(pet, 150, until=lambda p, _v: p.scene is None)


def test_the_menu_game_ends_with_the_ball_popped_and_the_cat_lying_on_it():
    for seed in range(4):
        pet, trace = game(seed)
        seen = names(trace)
        assert pet.scene is None and pet.ball is None, seed
        assert "beach_pat" in seen
        order = ["beach_pounce", "beach_flat", "beach_flat_fade", "beach_getup", "sit_up"]
        tail = seen[seen.index("beach_pounce"):]
        assert [tail.index(n) for n in order] == sorted(tail.index(n) for n in order), seed


def test_the_ball_rolls_in_and_is_drawn_with_its_own_frames():
    pet, trace = game(1)
    balls = [v.ball for v, _x, _i in trace if v.ball is not None and v.ball.visible]
    assert balls and {b.anim for b in balls} == {"beach_ball"}
    assert balls[0].x < 100 or balls[0].x > 1820  # arrivé d'un bord de l'écran


def test_the_real_ball_hides_while_the_cat_draws_it():
    for seed in range(3):
        pet, trace = game(seed)
        drawn = [v for v, _x, i in trace
                 if v.animation in DRAWN or (v.animation == "beach_pat" and i < BEACH_LAUNCH[0])]
        assert drawn and all(v.ball is None or not v.ball.visible for v in drawn), seed


def test_a_pat_sends_the_ball_rolling_from_under_the_paw():
    launched = 0
    for seed in range(4):
        pet = settled_pet(seed, 800)
        pet.ball = Ball(1000, 1080, kind=BEACH)
        pet.ball.update(DT, SNAP, compute_surfaces(SNAP))
        pet.request("beachball")
        trace = run(pet, 60, until=lambda p, v: v.animation == "beach_pat" and p.player.index >= BEACH_LAUNCH[0])
        view, cat_x, _i = trace[-1]
        if view.animation != "beach_pat":
            continue
        side = -1 if view.mirrored else 1
        assert view.ball.visible and abs(view.ball.x - (cat_x + side * BEACH_LAUNCH[1])) < 15
        later = run(pet, 1)
        assert all(v.ball is None or (v.ball.x - view.ball.x) * side >= 0 for v, _x, _i in later)
        assert later[-1][0].ball is not None and abs(later[-1][0].ball.x - view.ball.x) > 40  # il roule
        launched += 1
    assert launched >= 2


def test_the_cat_sits_right_beside_the_ball_before_patting_it():
    checked = 0
    for seed in range(4):
        pet = settled_pet(seed, 800)
        pet.ball = Ball(1100, 1080, kind=BEACH)
        pet.ball.update(DT, SNAP, compute_surfaces(SNAP))
        pet.request("beachball")
        run(pet, 60, until=lambda p, v: v.animation in ("beach_sit", "beach_pat", "beach_pounce"))
        side = -1 if pet.mirrored else 1
        if pet.ball is not None:
            assert pet.ball.x == pet.body.x + side * BEACH.at_feet
            checked += 1
    assert checked >= 2


def test_a_beach_ball_lying_around_tempts_the_cat():
    played = False
    for seed in range(3):
        pet = settled_pet(seed, 400)
        pet.ball = Ball(1200, 1080, kind=BEACH)
        pet.ball.update(DT, SNAP, compute_surfaces(SNAP))
        seen = names(run(pet, 150, until=lambda _p, v: v.animation == "beach_pat"))
        played |= seen[-1] == "beach_pat"
        assert "yarn_bat" not in seen
    assert played


def test_no_beach_ball_game_without_the_extension():
    anims = {k: v for k, v in make_anims().items() if not k.startswith("beach_")}
    pet = settled_pet(1, 800, anims=anims)
    pet.request("beachball")
    run(pet, 5)
    assert pet.ball is None and pet.scene is None


def test_a_ball_lying_under_the_cats_own_window_does_not_make_him_hop_on_the_spot():
    win = WinRect(1, Rect(700, 700, 1220, 380))  # collée au bord droit, jusqu'au sol
    snap = WorldSnapshot(monitors=(SCREEN,), windows=(win,), cursor=None)
    segs = compute_surfaces(snap)
    pet = Pet(make_anims(), rng=random.Random(0), needs=Needs(0.1, 0.1))
    pet.update(DT, snap)
    top = next(s for s in segs if s.owner == 1)
    pet.mode = "script"
    pet.body.x, pet.body.y, pet.body.support = 1100, top.y, top
    pet.body.vx = pet.body.vy = 0.0
    pet.ball = Ball(1087, 1080, kind=BEACH)
    pet.ball.update(DT, snap, segs)
    pet.ball.support = next(s for s in segs if s.owner is None)
    assert pet._leap_to_ball() is None  # le saut retomberait sur sa propre fenêtre
    pet._run(pet._brain())
    trace = []
    for _ in range(int(60 / DT)):
        trace.append(pet.update(DT, snap).animation)
    hops = sum(1 for a, b in zip(trace, trace[1:]) if b.startswith("jump_land") and not a.startswith("jump_land"))
    assert hops <= 1


def test_the_final_pounce_is_not_played_off_the_screen():
    for seed, x0 in ((1, 40), (1, 1880), (4, 1880), (8, 1880)):
        _pet, trace = game(seed, x0)
        for view, x, _i in trace:
            if view.animation == "beach_pounce":
                reach = x - 112 if view.mirrored else x + 112  # la planche 501 va jusqu'à 111 px des pieds
                assert 0 <= reach <= 1920, (seed, x0)
