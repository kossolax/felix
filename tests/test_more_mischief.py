"""Extension More Mischief : la déchirure dans l'écran, le papillon, le tas de feuilles."""
import random

from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.world import Monitor, Rect, WorldSnapshot
from tests.anim_helpers import make_anims

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
SNAP = WorldSnapshot(monitors=(SCREEN,), windows=(), cursor=None)
BUTTERFLY = ["butterfly_arrive", "butterfly_nose", "butterfly_sit", "butterfly_follow", "butterfly_look_up",
             "butterfly_swipe", "butterfly_on_face", "butterfly_off_face", "butterfly_hover", "butterfly_swat",
             "butterfly_getup", "butterfly_leap", "butterfly_land", "butterfly_head", "butterfly_swat_again",
             "butterfly_leave"]


def settled_pet(seed=5, x=None, anims=None):
    pet = Pet(anims or make_anims(), rng=random.Random(seed), needs=Needs(0.1, 0.1))
    for _ in range(int(4 / DT)):
        pet.update(DT, SNAP)
    if x is not None:
        pet.body.x = x
    return pet


def scene(pet, name, seconds=120):
    pet.request(name)
    trace, started = [], False
    for _ in range(int(seconds / DT)):
        view = pet.update(DT, SNAP)
        trace.append(view)
        started |= pet.scene == name
        if started and pet.scene != name:
            break
    return trace


def in_order(trace, names):
    seen = [v.animation for v in trace]
    return all(n in seen for n in names) and [seen.index(n) for n in names] == sorted(seen.index(n) for n in names)


def prop_anims(trace):
    return [e for v in trace for e in v.events if isinstance(e, tuple) and e[0] == "prop_anim"]


def test_the_cat_tears_the_screen_hides_inside_and_the_tear_closes_behind_him():
    for x in (600, 1860):  # la place manque à droite : la scène se joue en miroir
        pet = settled_pet(1, x)
        trace = scene(pet, "tear")
        assert in_order(trace, ["tear_scratch", "tear_enter", "tear_inside", "tear_emerge", "tear_walk_off"]), x
        (event,) = prop_anims(trace)
        _, name, (ox, oy), mirrored = event
        assert name == "tear_close" and oy < 1080
        assert mirrored or x < 1000  # sans place à droite, la scène se joue en miroir
        emitted = next(i for i, v in enumerate(trace) if event in v.events)
        assert trace[emitted - 1].animation == "tear_walk_off"


def test_the_cat_hidden_in_the_tear_cannot_be_grabbed_nor_stroked():
    pet = settled_pet(2, 600)
    pet.request("tear")
    for _ in range(int(60 / DT)):
        if pet.update(DT, SNAP).animation == "tear_inside":
            break
    pet.grab(pet.body.x, pet.body.y - 30)
    pet.stroke()
    assert pet.mode != "held" and pet.update(DT, SNAP).animation == "tear_inside"


def test_the_butterfly_scene_plays_through():
    for x in (500, 1880):
        pet = settled_pet(3, x)
        trace = scene(pet, "butterfly")
        assert in_order(trace, BUTTERFLY), x
        after = [v.animation for v in trace[[v.animation for v in trace].index("butterfly_leave"):]]
        assert any(a.startswith("walk_") for a in after), x  # puis il repart en marchant (script 0x3ec)


def test_the_scene_plays_facing_right_when_there_is_room_on_both_sides():
    for seed in range(6):
        pet = settled_pet(seed, 900)
        trace = scene(pet, "butterfly")
        assert not any(v.mirrored for v in trace if v.animation.startswith("butterfly_")), seed


def test_the_cat_stops_on_the_first_frame_of_his_standing_pose_before_the_scene():
    for name, first in (("tear", "tear_scratch"), ("butterfly", "butterfly_arrive"), ("leaves", "leaves_appear")):
        pet = settled_pet(2, 900)
        trace = scene(pet, name)
        i = [v.animation for v in trace].index(first)
        assert trace[i - 1].animation.startswith("stand_") and trace[i - 1].frame == make_anims()[
            trace[i - 1].animation].frames[0], name  # la pose qui raccorde avec la 1re image


def test_the_leaves_scene_keeps_the_original_rounds():
    pet = settled_pet(4, 700)
    seen = [v.animation for v in scene(pet, "leaves")]
    runs = [a for i, a in enumerate(seen) if i == 0 or seen[i - 1] != a]
    for name, count in (("leaves_stalk", 3), ("leaves_back", 1), ("leaves_lie", 1)):
        total = seen.count(name)
        one = len(make_anims()[name].frames) / make_anims()[name].fps * 30
        assert round(total / one) == count, name
    assert runs


def test_the_cat_dives_into_a_pile_of_leaves_which_then_fades():
    pet = settled_pet(4, 700)
    trace = scene(pet, "leaves")
    assert in_order(trace, ["leaves_appear", "leaves_stalk", "leaves_pounce", "leaves_dive", "leaves_roll",
                            "leaves_lie", "leaves_getup", "leaves_shake", "leaves_cross", "leaves_walk_off"])
    assert [e[1] for e in prop_anims(trace)] == ["leaves_fade"]


def test_more_mischief_happens_on_its_own():
    seen = set()
    for seed in range(5):
        pet = settled_pet(seed, 900)
        for _ in range(int(500 / DT)):
            a = pet.update(DT, SNAP).animation
            if a.startswith(("tear_", "butterfly_", "leaves_")):
                seen.add(a.split("_")[0])
    assert len(seen) >= 2


def test_prop_animation_plays_then_closes(qapp):
    from PySide6.QtGui import QColor, QImage
    from felix.core.anim import Animation, Frame
    from felix.render.props import PropManager
    from felix.render.sprites import SpriteBank
    img = QImage(30, 10, QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255, 255))
    frames = tuple(Frame(1, (i * 10, 0, 10, 10), (5, 9)) for i in range(3))
    bank = SpriteBank({1: img}, {"fade": Animation("fade", 1, frames, fps=10)})
    props = PropManager(bank, lifetime=60)
    props.handle(("prop_anim", "fade", (500, 900), False))
    (w,) = props.windows
    assert (w.x(), w.y(), w.width(), w.height()) == (500, 900, 10, 10)
    for _ in range(3):
        w.advance()
    assert not w.isVisible()
