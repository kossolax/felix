"""Extension Kitten : un chaton qui suit Felix, et leurs scènes à deux (lait, queue, câlin et
transport, chatière). Seul, il a sa fenêtre ; avec Felix, les images de Felix le dessinent."""
import random

from felix.core.kitten import KPlay, KWalk, Kitten
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
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


def on_window_with_kitten(seed, snap, x=900):
    """Felix et le chaton sur la fenêtre 1 de `snap`."""
    pet = Pet(make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.5))
    pet.update(DT, snap)
    top = next(s for s in compute_surfaces(snap) if s.owner == 1)
    pet.mode = "script"
    pet.body.x, pet.body.y, pet.body.support = x, top.y, top
    pet.body.vx = pet.body.vy = 0.0
    pet._run(pet._brain())
    pet.show_kitten()
    for _ in range(int(40 / DT)):
        pet.update(DT, snap)
        if pet.kitten is not None and pet.scene is None:
            break
    assert pet.kitten is not None and pet.kitten.support == pet.body.support
    return pet


def window(x=400, y=600, w=1200):
    return WorldSnapshot(monitors=(SCREEN,), windows=(WinRect(1, Rect(x, y, w, 1080 - y)),), cursor=None)


def test_the_kitten_comes_back_when_a_scene_together_is_cut_short():
    snap = window()
    pet = on_window_with_kitten(4, snap)
    pet.request("kitten_tail")
    for _ in range(int(40 / DT)):
        pet.update(DT, snap)
        if pet.kitten.puppet:
            break
    assert pet.kitten.puppet  # dessiné par les images de Felix
    gone = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)  # la fenêtre se ferme : il tombe
    seen = [pet.update(DT, gone).kitten for _ in range(int(8 / DT))]
    assert seen[-1] is not None and seen[-1].visible
    pet.hide_kitten()
    run(pet, 20, until=lambda p, _v: p.kitten is None)
    assert pet.kitten is None  # et on peut encore le cacher


def test_picking_up_the_cat_while_he_waits_for_the_kitten_frees_it():
    pet = with_kitten(3)
    pet.request("kitten_rub")
    run(pet, 20, until=lambda p, _v: p.kitten.goal is not None)
    assert pet.kitten.goal is not None
    pet.grab(pet.body.x, pet.body.y - 30)
    pet.release()
    run(pet, 3)
    assert pet.kitten.goal is None and not pet.kitten.ready


def test_the_kitten_can_be_hidden_while_it_is_being_shown():
    pet = settled_pet(1)
    pet.show_kitten()
    run(pet, 1.5)
    assert pet.kitten is None and pet.kitten_coming
    pet.hide_kitten()
    trace = run(pet, 60, until=lambda p, _v: p.scene is None and p.kitten is None)
    assert pet.kitten is None and not pet.kitten_coming
    assert "kitten_appear" in names(trace)  # la scène va au bout, puis il s'efface


def test_a_scene_together_moves_along_with_its_window():
    snap = window()
    pet = on_window_with_kitten(4, snap)
    pet.request("kitten_tail")
    for _ in range(int(40 / DT)):
        pet.update(DT, snap)
        if pet.kitten.puppet:
            break
    moved = window(x=500)  # la fenêtre glisse de 100 px pendant la scène
    for _ in range(int(30 / DT)):
        pet.update(DT, moved)
        if not pet.kitten.puppet:
            break
    assert pet.kitten.visible
    assert -40 < pet.kitten.x - pet.body.x < 0  # derrière Felix, où ses images l'ont laissé (pas 100 px plus loin)


def test_the_cat_leaves_room_for_the_kitten_near_the_left_end():
    for scene in ("kitten_tail", "kitten_rub"):
        pet = with_kitten(4, 1000)
        pet.kitten.x = 500  # de l'autre côté, à portée
        pet.body.x = 45
        pet.request(scene)
        seen = names(run(pet, 60, until=lambda p, _v: p.scene is None and p.kitten.visible))
        assert any(n.startswith(("kitten_tail_", "kitten_rub_")) for n in seen), scene


def test_the_kitten_keeps_out_of_the_milk_bowl():
    pet = with_kitten(2)
    pet.kitten.x = pet.body.x + 60  # juste là où la gamelle va apparaître
    pet.hold_item("carton")
    run(pet, 4)
    pet.serve()
    for view, cat_x in run(pet, 15, until=lambda p, _v: p.player.animation.name == "carton_lap"):
        if view.animation.startswith("carton_") and view.kitten is not None and view.kitten.visible:
            assert not cat_x - 55 < view.kitten.x < cat_x + 125


def test_the_kitten_sits_down_where_it_stands_up():
    anims = make_anims()
    assert anims["kitten_sit"].enter[0] == -anims["kitten_sit_up"].shift[0]  # 728:0 est dessinée 11 px plus loin


def test_the_kitten_walks_at_its_drawn_pace_at_double_size():
    anims = make_anims(scale=2)
    kitten = Kitten(anims, 400, 1080, scale=2)
    kitten.support = compute_surfaces(SNAP)[0]
    kitten.run(iter([KWalk(1400)] + [KPlay("kitten_stand_right", duration=60)]))
    xs = []
    for _ in range(10):
        kitten.update(DT, None, SNAP, compute_surfaces(SNAP))
        xs.append(kitten.x)
    speed = (xs[-1] - xs[0]) / (9 * DT)
    assert abs(speed - anims["kitten_trot_right"].dx * 10) < 25  # 2 × 6 px par image, 10 images/s
