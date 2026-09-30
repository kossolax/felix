"""Extension Mischief : griffures sur la vitre, plante en pot renversée, corbeille fouillée.
Des bêtises que le chat fait de lui-même (l'original n'avait pas de menu pour elles)."""
import random

from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.world import Monitor, Rect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
SNAP = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)


def settled_pet(seed=5, x=None, anims=None, facing=None):
    pet = Pet(anims or make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, SNAP)
    if x is not None:
        pet.body.x = x
    return pet


def scene(pet, name, seconds=90):
    pet.request(name)
    trace, events, started = [], [], False
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, SNAP)
        trace.append((view.animation, pet.body.x))
        events.extend(view.events)
        started |= pet.scene == name
        if started and pet.scene is None:
            break
    return trace, events


def marks(events):
    return [e for e in events if isinstance(e, tuple) and e[0] == "marks"]


def first_and_last(trace, prefix):
    xs = [x for a, x in trace if a.startswith(prefix)]
    return xs[0], trace[next(i for i in range(len(trace) - 1, -1, -1) if trace[i][0].startswith(prefix)) + 1][1]


def test_the_cat_scratches_the_glass_and_leaves_claw_marks():
    for facing in ("left", "right"):
        pet = settled_pet(1, 900)
        pet.facing = facing
        trace, events = scene(pet, "scratch")
        seen = [a for a, _x in trace]
        order = [f"glass_scratch_{facing}_rise", f"glass_scratch_{facing}", f"glass_scratch_{facing}_down",
                 f"glass_scratch_{facing}_leave"]
        assert [seen.index(n) for n in order] == sorted(seen.index(n) for n in order), facing
        start, end = first_and_last(trace, "glass_scratch_")
        assert end - start == (-97 if facing == "left" else 97)  # il repart dans le même sens
        assert len(marks(events)) == 1 and len(marks(events)[0][1]) == 1  # les rayures restent


def test_the_cat_knocks_over_a_potted_plant_and_leaves_a_mess():
    pet = settled_pet(2, 900)
    trace, events = scene(pet, "plant")
    seen = [a for a, _x in trace]
    order = ["plant_appear", "plant_sniff", "plant_circle", "plant_knock", "plant_trample", "plant_chew",
             "plant_pull", "plant_tangled", "plant_leave", "plant_leave_end"]
    assert [seen.index(n) for n in order] == sorted(seen.index(n) for n in order)
    start, end = first_and_last(trace, "plant_")
    assert end - start == -18
    assert len(marks(events)) == 1 and len(marks(events)[0][1]) == 5  # pot, terre, plante, traces


def test_the_cat_raids_the_recycle_bin_and_everything_vanishes():
    pet = settled_pet(3, 900)
    trace, events = scene(pet, "bin")
    seen = [a for a, _x in trace]
    order = ["bin_appear", "bin_sniff", "bin_crouch", "bin_pounce", "bin_papers", "bin_rummage", "bin_end"]
    assert [seen.index(n) for n in order] == sorted(seen.index(n) for n in order)
    start, end = first_and_last(trace, "bin_")
    assert end - start == 111
    assert marks(events) == []


def test_mischief_needs_room_so_the_cat_first_moves_away_from_the_edge():
    pet = settled_pet(1, 1920 - 60)
    trace, _ = scene(pet, "bin")
    xs = [x for a, x in trace if a == "bin_appear"]
    assert xs and 1920 - xs[0] >= 235


def test_the_cat_gets_up_to_mischief_on_its_own():
    seen = set()
    for seed in range(4):
        pet = settled_pet(seed, 900)
        for _ in range(int(400 / DT)):
            a = pet.update(DT, SNAP).animation
            if a.startswith(("glass_scratch_", "plant_", "bin_")):
                seen.add(a.split("_")[0])
    assert len(seen) >= 2


def test_no_extension_mischief_without_the_extension():
    anims = {k: v for k, v in make_anims().items() if not k.startswith(("glass_scratch_", "plant_", "bin_"))}
    for seed in range(2):
        pet = settled_pet(seed, 900, anims=anims)
        for _ in range(int(300 / DT)):
            pet.update(DT, SNAP)
        pet.request("plant")
        for _ in range(int(3 / DT)):
            assert not pet.update(DT, SNAP).animation.startswith("plant_")
