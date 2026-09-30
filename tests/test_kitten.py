"""Extension Kitten : un chaton qui suit Felix, et leurs scènes à deux (lait, queue, câlin et
transport, chatière). Seul, il a sa fenêtre ; avec Felix, les images de Felix le dessinent."""
import random

from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.world import Monitor, Rect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
SNAP = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)


def settled_pet(seed=5, x=900, anims=None):
    pet = Pet(anims or make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.5))
    for _ in range(int(4 / DT)):
        pet.update(DT, SNAP)
    pet.body.x = x
    return pet


def run(pet, seconds, until=None):
    out = []
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, SNAP)
        out.append((view, pet.body.x))
        if until is not None and until(pet, view):
            break
    return out


def with_kitten(seed=5, x=900):
    pet = settled_pet(seed, x)
    pet.show_kitten()
    run(pet, 40, until=lambda p, _v: p.kitten is not None and p.scene is None)
    assert pet.kitten is not None
    return pet


def names(trace):
    return [v.animation for v, _x in trace]


def test_showing_the_kitten_it_appears_beside_the_sitting_cat():
    pet = settled_pet(1)
    pet.show_kitten()
    trace = run(pet, 40, until=lambda p, _v: p.kitten is not None)
    assert "kitten_appear" in names(trace)
    view, cat_x = trace[-1]
    assert view.kitten is not None and view.kitten.visible
    assert (pet.kitten.x, view.kitten.y) == (cat_x + 43, 1080 - 2)  # relais au pixel, Felix assis


def test_the_kitten_follows_the_cat():
    pet = with_kitten(2)
    pet.still = True  # Felix ne bouge plus
    pet.body.x = pet.kitten.x + 600
    run(pet, 20)
    assert abs(pet.kitten.x - pet.body.x) < 120
    seen = {v.kitten.anim for v, _x in run(pet, 1) if v.kitten}
    assert seen


def test_the_kitten_rubs_against_the_cat_who_carries_it_off():
    pet = with_kitten(3)
    pet.request("kitten_rub")
    trace = run(pet, 60, until=lambda p, _v: p.scene is None and p.kitten is not None and p.kitten.visible)
    seen = names(trace)
    order = ["kitten_rub_approach", "kitten_rub_along", "kitten_rub_nuzzle", "kitten_pickup", "kitten_carry_right",
             "kitten_put_down_right"]
    assert [seen.index(n) for n in order] == sorted(seen.index(n) for n in order)
    drawn = [v for v, _x in trace if v.animation.startswith(("kitten_rub_", "kitten_pickup", "kitten_carry_",
                                                            "kitten_put_down_"))]
    assert all(v.kitten is None or not v.kitten.visible for v in drawn)  # dessiné par les images de Felix
    i = max(k for k, (v, _x) in enumerate(trace) if v.animation == "kitten_put_down_right")
    view, cat_x = trace[i + 1]
    assert view.kitten.visible and pet.kitten.x == cat_x + 38


def test_the_kitten_plays_with_the_cats_tail():
    pet = with_kitten(4)
    pet.request("kitten_tail")
    trace = run(pet, 60, until=lambda p, _v: p.scene is None and p.kitten is not None and p.kitten.visible)
    seen = names(trace)
    assert seen.index("kitten_tail_sit") < seen.index("kitten_tail_stalk") < seen.index("kitten_tail_play")
    assert pet.kitten.visible


def test_the_kitten_cannot_follow_the_cat_through_its_flap():
    pet = with_kitten(5)
    pet.request("kitten_flap")
    trace = run(pet, 80, until=lambda p, _v: p.scene is None and p.kitten is not None and p.kitten.visible)
    seen = names(trace)
    order = ["kitten_flap_appear", "kitten_flap_through", "kitten_flap_push", "kitten_flap_wait", "kitten_flap_leave"]
    assert [seen.index(n) for n in order] == sorted(seen.index(n) for n in order)


def test_hiding_the_kitten_it_sits_and_fades_away():
    pet = with_kitten(6)
    pet.hide_kitten()
    trace = run(pet, 20, until=lambda p, _v: p.kitten is None)
    assert pet.kitten is None
    assert any(v.kitten is not None and v.kitten.anim == "kitten_fade" for v, _x in trace)


def test_the_kitten_can_be_picked_up_and_dropped():
    pet = with_kitten(7)
    pet.grab_kitten()
    pet.drag_kitten(pet.kitten.x + 100, 600)
    assert pet.update(DT, SNAP).kitten.anim == "kitten_held"
    pet.release_kitten()
    trace = run(pet, 5)
    seen = [v.kitten.anim for v, _x in trace if v.kitten]
    assert "kitten_fall" in seen and "kitten_land" in seen and pet.kitten.y == 1080


def test_the_cat_and_the_kitten_play_together_on_their_own():
    seen = set()
    for seed in range(3):
        pet = with_kitten(seed)
        for view, _x in run(pet, 300):
            if view.animation.startswith(("kitten_rub_", "kitten_tail_", "kitten_flap_")):
                seen.add(view.animation.split("_")[1])
    assert len(seen) >= 2


def test_no_kitten_without_the_extension():
    anims = {k: v for k, v in make_anims().items() if not k.startswith("kitten_")}
    pet = settled_pet(1, anims=anims)
    pet.show_kitten()
    run(pet, 10)
    assert pet.kitten is None
