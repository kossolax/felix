from felix.core.physics import Body, step
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot

SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))


def world(*windows):
    return WorldSnapshot(monitors=(SCREEN,), windows=tuple(windows))


def run(body, snap, seconds, dt=1 / 30):
    for _ in range(int(seconds / dt)):
        step(body, dt, snap, compute_surfaces(snap))
    return body


def test_a_falling_body_lands_on_the_first_edge_below():
    snap = world(WinRect(1, Rect(100, 500, 400, 300)))
    body = run(Body(x=200, y=100), snap, 2)
    assert (body.y, body.vy, body.support.owner) == (500, 0, 1)


def test_a_body_on_a_window_follows_it_when_it_moves():
    body = run(Body(x=200, y=100), world(WinRect(1, Rect(100, 500, 400, 300))), 2)
    moved = world(WinRect(1, Rect(150, 450, 400, 300)))
    run(body, moved, 1 / 30)
    assert (body.x, body.y) == (250, 450)


def test_a_body_falls_when_its_window_closes():
    body = run(Body(x=200, y=100), world(WinRect(1, Rect(100, 500, 400, 300))), 2)
    body = run(body, world(), 2)
    assert (body.y, body.support.owner) == (1080, None)


def test_a_body_falls_when_another_window_covers_its_spot():
    base = WinRect(1, Rect(100, 500, 400, 300))
    body = run(Body(x=200, y=100), world(base), 2)
    body = run(body, world(WinRect(2, Rect(150, 400, 200, 300)), base), 2)
    assert body.support.owner == 2 or body.y > 500


def test_standing_body_does_not_move_without_changes():
    body = run(Body(x=200, y=100), world(), 3)
    assert (body.x, body.y, body.vy) == (200, 1080, 0)
