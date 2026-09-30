from felix.core.ball import BALL_FRICTION, Ball
from felix.core.surfaces import compute_surfaces
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot

DT = 1 / 30
SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))


def world(*windows):
    return WorldSnapshot(monitors=(SCREEN,), windows=tuple(windows))


def run(ball, snap, seconds, trace=None):
    segs = compute_surfaces(snap)
    for _ in range(int(seconds / DT)):
        ball.update(DT, snap, segs)
        if trace is not None:
            trace.append((ball.x, ball.y, ball.vy, ball.frame, ball.support))


def on_floor(x, snap):
    ball = Ball(x, 1080)
    run(ball, snap, DT)  # se pose
    assert ball.resting and ball.support.owner is None
    return ball


def test_a_kicked_ball_rolls_slower_and_slower_then_stops():
    snap = world()
    ball = on_floor(500, snap)
    ball.kick(300, 0)
    trace = []
    run(ball, snap, 3, trace)
    assert ball.resting and ball.y == 1080
    assert abs(ball.x - (500 + 300 ** 2 / (2 * BALL_FRICTION))) < 15
    steps = [b[0] - a[0] for a, b in zip(trace, trace[1:])]
    assert steps[0] > steps[5] > steps[10] >= 0


def test_the_ball_turns_as_it_rolls_one_way_or_the_other():
    snap = world()
    for vx, step in ((250, 1), (-250, -1)):
        ball = on_floor(900, snap)
        ball.kick(vx, 0)
        trace = []
        run(ball, snap, 1, trace)
        frames = [f for _x, _y, _vy, f, _s in trace]
        changes = [(b - a) % 4 for a, b in zip(frames, frames[1:]) if a != b]
        assert len(changes) >= 3 and set(changes) == {step % 4}


def test_the_ball_bounces_off_the_edge_of_the_screen():
    snap = world()
    ball = on_floor(1850, snap)
    ball.kick(500, 0)
    trace = []
    run(ball, snap, 4, trace)
    assert max(x for x, *_ in trace) < 1920
    assert ball.resting and ball.x < 1850


def test_a_ball_rolling_off_a_window_falls_bounces_and_lands_on_the_floor():
    snap = world(WinRect(1, Rect(400, 700, 500, 380)))
    segs = compute_surfaces(snap)
    ball = Ball(850, 700)
    ball.update(DT, snap, segs)
    assert ball.support is not None and ball.support.owner == 1
    ball.kick(300, 0)
    trace = []
    run(ball, snap, 5, trace)
    assert ball.resting and ball.support.owner is None and ball.x > 900
    falling = [i for i, t in enumerate(trace) if t[4] is None]
    assert falling
    after_fall = trace[falling[0]:]
    assert any(vy < 0 for _x, _y, vy, _f, _s in after_fall)  # rebondit au sol


def test_a_window_in_front_is_a_wall_for_a_ball_rolling_on_the_window_behind():
    front = WinRect(2, Rect(900, 500, 400, 580))  # devant, recouvre le bord de la fenêtre de derrière
    back = WinRect(1, Rect(400, 700, 1000, 380))
    snap = world(front, back)
    segs = compute_surfaces(snap)
    ball = Ball(800, 700)
    ball.update(DT, snap, segs)
    ball.kick(400, 0)
    trace = []
    run(ball, snap, 4, trace)
    assert max(x for x, *_ in trace) <= 900
    assert ball.resting and ball.support.owner == 1


def test_the_ball_rides_a_moving_window_and_falls_when_it_closes():
    win = WinRect(1, Rect(400, 700, 500, 380))
    ball = Ball(600, 700)
    run(ball, world(win), DT)
    moved = WinRect(1, Rect(500, 650, 500, 380))
    run(ball, world(moved), DT)
    assert (ball.x, ball.y) == (700, 650) and ball.support.owner == 1
    run(ball, world(), 3)
    assert ball.resting and ball.support.owner is None and ball.y == 1080


def test_a_thrown_ball_flies_and_lands_on_the_floor():
    snap = world()
    ball = on_floor(1000, snap)
    ball.grab()
    ball.move_to(1000, 300)
    run(ball, snap, 1)
    assert (ball.x, ball.y) == (1000, 300)  # tenue : pas de gravité
    ball.throw(-600, -200)
    run(ball, snap, 6)
    assert ball.resting and ball.y == 1080 and ball.x < 1000


def test_a_ball_sent_away_rolls_off_the_screen_and_is_gone():
    snap = world()
    ball = on_floor(1700, snap)
    ball.exits = True
    ball.kick(150, 0)
    run(ball, snap, 3)
    assert ball.gone


def test_scale_makes_the_ball_roll_further():
    snap = world()
    small, big = on_floor(300, snap), Ball(300, 1080, scale=2)
    run(big, snap, DT)
    small.kick(200, 0)
    big.kick(400, 0)
    run(small, snap, 4)
    run(big, snap, 4)
    assert abs((big.x - 300) - 2 * (small.x - 300)) < 10
