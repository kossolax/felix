import random

from felix.core.pet import Pet
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))


def world(*windows, cursor=None):
    return WorldSnapshot(monitors=(SCREEN,), windows=tuple(windows), cursor=cursor)


def run(pet, snap, seconds, check=None):
    view = None
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, snap)
        if check:
            check(pet, view)
    return view


def new_pet(seed=1):
    return Pet(make_anims(), rng=random.Random(seed))


def test_pet_enters_through_the_flap_on_the_floor():
    pet = new_pet()
    view = pet.update(DT, world())
    assert view.animation == "enter_flap"
    assert pet.body.y == 1080
    run(pet, world(), 4)
    assert pet.player.animation.name != "enter_flap"
    assert pet.body.grounded


def test_held_pet_follows_the_pointer():
    pet = new_pet()
    run(pet, world(), 4)
    x, y = pet.body.x, pet.body.y
    pet.grab(x, y - 20)
    pet.drag(x + 100, y - 320)
    view = pet.update(DT, world())
    assert (pet.body.x, pet.body.y) == (x + 100, y - 300)
    assert view.animation.startswith("held")


def test_released_pet_falls_then_lands():
    pet = new_pet()
    run(pet, world(), 4)
    pet.grab(pet.body.x, pet.body.y)
    pet.drag(500, 200)
    pet.release()
    view = pet.update(DT, world())
    assert view.animation.startswith("fall")
    run(pet, world(), 2)
    assert pet.body.grounded and pet.body.y == 1080


def test_grounded_pet_always_stands_on_its_support():
    snap = world(WinRect(1, Rect(300, 600, 700, 300)), WinRect(2, Rect(900, 350, 500, 400)))
    segs = compute_surfaces(snap)

    def check(pet, view):
        s = pet.body.support
        if s is not None and pet.mode == "script":
            assert s in segs and s.x0 <= pet.body.x < s.x1

    for seed in range(5):
        run(new_pet(seed), snap, 60, check)


def test_pet_uses_windows_as_platforms_eventually():
    snap = world(WinRect(1, Rect(300, 800, 1200, 200)))
    owners = set()

    def check(pet, view):
        if pet.body.support is not None:
            owners.add(pet.body.support.owner)

    for seed in range(4):
        run(new_pet(seed), snap, 90, check)
    assert 1 in owners


def test_stand_still_keeps_the_pet_in_place():
    pet = new_pet()
    run(pet, world(), 4)
    pet.still = True
    x = pet.body.x
    run(pet, world(), 30, lambda p, v: None)
    assert pet.body.x == x


def test_pet_hides_while_a_fullscreen_window_is_on_top():
    pet = new_pet()
    run(pet, world(), 4)
    assert run(pet, world(WinRect(3, Rect(0, 0, 1920, 1080), fullscreen=True)), 0.1).hidden
    assert not run(pet, world(), 0.1).hidden


def test_pet_climbs_windows_of_a_recorded_gnome_scene():
    from pathlib import Path
    from felix.platform.fake import load_scene
    snap = load_scene(Path(__file__).parent / "scenes" / "gnome46_x11_gedit_xclock.json")
    owners = set()

    def check(pet, view):
        if pet.body.support is not None:
            owners.add(pet.body.support.owner)

    run(new_pet(0), snap, 180, check)
    assert {w.id for w in snap.windows} & owners


def test_a_bigger_cat_has_its_head_higher():
    small, big = Pet(make_anims()), Pet(make_anims(), scale=2)
    for pet in (small, big):
        pet.update(DT, world())
    assert (big.body.y - big.head()[1]) == 2 * (small.body.y - small.head()[1])


def test_fullscreen_on_another_monitor_does_not_hide_the_cat():
    left = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
    right = Monitor(Rect(1920, 0, 1920, 1080), Rect(1920, 0, 1920, 1080))
    video = WinRect(7, Rect(1920, 0, 1920, 1080), fullscreen=True)
    pet = new_pet()
    snap = WorldSnapshot(monitors=(left, right), windows=(video,))
    pet.update(DT, snap)
    pet.body.x = 500  # sur l'écran de gauche
    assert not pet.update(DT, snap).hidden
    pet.body.x = 2500  # sur l'écran de droite, sous la vidéo
    assert pet.update(DT, snap).hidden
