from felix.core.anim import Animation, Frame, Player


def make_anim(n, fps=10, loop=False):
    frames = tuple(Frame(sheet=1, rect=(i * 10, 0, 10, 10), anchor=(5, 10)) for i in range(n))
    return Animation(name="a", sheet=1, frames=frames, fps=fps, loop=loop)


def test_advances_one_frame_per_period():
    p = Player(make_anim(5))
    assert p.index == 0
    steps = p.update(0.25)
    assert (p.index, steps) == (2, 2)


def test_loop_wraps_around():
    p = Player(make_anim(3, loop=True))
    p.update(0.35)
    assert p.index == 0
    assert not p.finished


def test_one_shot_holds_last_frame_then_finishes():
    p = Player(make_anim(3))
    p.update(0.25)
    assert (p.index, p.finished) == (2, False)
    p.update(0.1)
    assert (p.index, p.finished) == (2, True)


def test_frame_property_returns_current_frame():
    p = Player(make_anim(3))
    p.update(0.1)
    assert p.frame.rect == (10, 0, 10, 10)
