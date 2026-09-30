from felix.core.anim import Animation, Frame
from felix.core.pet import View
from felix.render.pet_window import Extents, compute_extents


def anim(*frames):
    return Animation(name="a", sheet=1, frames=tuple(frames))


def test_extents_cover_every_frame_around_the_feet_including_mirrored():
    a = anim(Frame(1, (0, 0, 100, 80), (30, 70)), Frame(1, (100, 0, 60, 90), (30, 90)))
    ext = compute_extents({"a": a})
    # gauche : max(30, 100-30=70 en miroir) ; droite : max(70, 30) ; haut : 90 ; bas : 10
    assert ext == Extents(left=70, right=70, up=90, down=10)
    assert (ext.width, ext.height) == (140, 100)


def test_frame_is_drawn_so_its_anchor_sits_on_the_feet_point():
    ext = Extents(left=70, right=70, up=90, down=10)
    f = Frame(1, (0, 0, 100, 80), (30, 70))
    assert ext.window_origin(View("a", f, 500.4, 300)) == (430, 210)
    assert ext.frame_offset(f, mirrored=False) == (40, 20)
    assert ext.frame_offset(f, mirrored=True) == (0, 20)


def test_extents_and_offset_account_for_layers_drawn_under_the_frame():
    # cellule 100×80, pieds en (30, 70) ; une télé 40×30 dessous, en (50, -20)
    f = Frame(1, (0, 0, 100, 80), (30, 70), under=((2, (0, 0, 40, 30), (50, -20)),))
    ext = compute_extents({"a": anim(f)})
    assert (ext.up, ext.down) == (90, 10)
    assert ext.frame_offset(f, mirrored=False) == (ext.left - 30, ext.up - 90)
