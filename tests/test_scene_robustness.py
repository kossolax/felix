"""Scènes des extensions face à l'utilisateur et au bureau : un clic, le menu, « Rester immobile »,
un bord d'écran, une fenêtre trop étroite ne doivent ni les casser ni téléporter le chat."""
import random

from felix.core.actions import Play, WalkTo
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
SNAP = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)


def settled_pet(seed=5, x=None, snap=SNAP):
    pet = Pet(make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, snap)
    if x is not None:
        pet.body.x = x
    return pet


def run(pet, seconds, snap=SNAP, until=None):
    trace = []
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, snap)
        trace.append((view.animation, pet.body.x))
        if until is not None and until(pet, view):
            break
    return trace


def on_window(pet, snap, owner, x):
    """Pose le chat, debout, sur la fenêtre `owner`."""
    seg = next(s for s in compute_surfaces(snap) if s.owner == owner)
    pet.mode = "script"
    pet.body.x, pet.body.y, pet.body.support = x, seg.y, seg
    pet.body.vx = pet.body.vy = 0.0
    pet._run(pet._brain())
    run(pet, 0.1, snap=snap)
    assert pet.body.support is not None and pet.body.support.owner == owner


def pick_once(pet, name):
    """Le prochain tirage du cerveau donne `name` (une bêtise qu'il fait de lui-même)."""
    real = pet.temper.pick

    def pick(choices):
        pet.temper.pick = real
        return name

    pet.temper.pick = pick
    pet.request("stand")  # le cerveau repart tout de suite, et tire au sort après
    pet._requests.clear()


def test_walking_away_from_beyond_the_margin_does_not_jump():
    pet = settled_pet(1, 1920 - 5)  # lâché tout au bord, au-delà de la marge

    def script():
        yield WalkTo(1920 - 300, idle=False)
        while True:
            yield Play("stand_left", duration=1.0)

    pet._run(script())
    xs = [x for _a, x in run(pet, 6, until=lambda p, _v: p.body.x <= 1920 - 300)]
    steps = [abs(b - a) for a, b in zip([1920 - 5] + xs, xs)]
    assert max(steps) <= 13 and xs[-1] <= 1920 - 300


def test_mischief_near_the_screen_edge_first_makes_its_room():
    for x in (1920 - 5, 5):
        pet = settled_pet(1, x)
        pet.request("bin")
        trace = run(pet, 30, until=lambda p, _v: p.player.animation.name == "bin_appear")
        assert trace[-1][0] == "bin_appear", x
        assert 60 <= trace[-1][1] <= 1920 - 235, x


def test_a_mischief_the_cat_chose_is_not_cut_short_by_a_click_or_the_menu():
    pet = settled_pet(2, 900)
    pick_once(pet, "bin")
    run(pet, 30, until=lambda p, _v: p.player.animation.name == "bin_rummage")
    assert pet.player.animation.name == "bin_rummage"
    pet.stroke()
    pet.request("drink")
    seen = [a for a, _x in run(pet, 40, until=lambda p, _v: p.player.animation.name.startswith("milk_"))]
    assert "bin_end" in seen and seen.index("bin_end") < len(seen) - 1  # la corbeille finit, puis le lait


def test_standing_still_lets_the_current_scene_finish():
    pet = settled_pet(2, 900)
    pet.request("leaves")
    run(pet, 30, until=lambda p, _v: p.player.animation.name == "leaves_roll")
    pet.still = True
    seen = [a for a, _x in run(pet, 40, until=lambda p, _v: p.scene is None)]
    assert "leaves_walk_off" in seen


def test_the_cat_cannot_be_picked_up_while_the_scene_draws_him_away_from_his_feet():
    pet = settled_pet(2, 900)
    pet.request("bin")
    run(pet, 30, until=lambda p, _v: p.player.animation.name == "bin_rummage")
    pet.grab(pet.body.x + 100, pet.body.y - 30)
    assert pet.mode == "script"
    seen = [a for a, _x in run(pet, 30, until=lambda p, _v: p.scene is None)]
    assert "bin_end" in seen


def test_no_long_mischief_on_a_window_too_narrow_for_it():
    win = WinRect(1, Rect(800, 500, 200, 300))
    snap = WorldSnapshot(monitors=(SCREEN,), windows=(win,), cursor=None)
    pet = settled_pet(3, snap=snap)
    on_window(pet, snap, 1, 900)
    offered = set(pet._mischief_ext()) | set(pet._more_mischief_ext())
    assert not offered & {"plant", "bin", "tear", "butterfly", "leaves"}
    pet.request("bin")  # même demandée, elle ne se joue pas dans le vide
    seen = [a for a, _x in run(pet, 5, snap=snap)]
    assert not any(a.startswith("bin_") for a in seen)
