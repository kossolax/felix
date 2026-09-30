from felix.core.surfaces import Segment, compute_surfaces, landing_between, support_at
from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot

SCREEN = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 32, 1920, 1048))  # top bar 32 px


def world(*windows):
    return WorldSnapshot(monitors=(SCREEN,), windows=tuple(windows))


def test_workarea_bottom_is_the_floor():
    assert compute_surfaces(world()) == [Segment(1080, 0, 1920, None)]


def test_window_top_edge_is_walkable():
    segs = compute_surfaces(world(WinRect(5, Rect(100, 300, 400, 200))))
    assert Segment(300, 100, 500, 5) in segs


def test_windows_above_hide_part_of_a_top_edge():
    top = WinRect(1, Rect(200, 250, 100, 200))  # couvre x 200..300 à y=300
    below = WinRect(2, Rect(100, 300, 400, 200))
    segs = compute_surfaces(world(top, below))
    assert Segment(300, 100, 200, 2) in segs
    assert Segment(300, 300, 500, 2) in segs
    assert not any(s.owner == 2 and s.x0 < 300 < s.x1 and s.x0 < 200 for s in segs if s.x0 != 100)


def test_window_touching_the_top_of_the_workarea_is_a_ceiling_not_a_floor():
    maximized = WinRect(9, Rect(0, 32, 1920, 1048))
    assert all(s.owner != 9 for s in compute_surfaces(world(maximized)))


def test_fullscreen_windows_are_ignored():
    assert all(s.owner != 4 for s in compute_surfaces(world(WinRect(4, Rect(0, 400, 800, 600), fullscreen=True))))


def test_edges_are_clipped_to_the_monitor():
    segs = compute_surfaces(world(WinRect(5, Rect(1800, 300, 400, 200))))
    assert Segment(300, 1800, 1920, 5) in segs


def test_support_at_needs_the_feet_on_the_segment():
    segs = [Segment(300, 100, 500, 5), Segment(1080, 0, 1920, None)]
    assert support_at(segs, 150, 300) == segs[0]
    assert support_at(segs, 150, 290) is None
    assert support_at(segs, 50, 300) is None


def test_landing_is_the_highest_segment_crossed_while_falling():
    segs = [Segment(1080, 0, 1920, None), Segment(600, 0, 500, 2), Segment(300, 100, 500, 5)]
    assert landing_between(segs, 150, 100, 700) == segs[2]
    assert landing_between(segs, 150, 301, 700) == segs[1]
    assert landing_between(segs, 700, 100, 700) is None


def test_floors_of_side_by_side_monitors_form_one_walkway():
    left = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))
    right = Monitor(Rect(1920, 0, 1920, 1080), Rect(1920, 0, 1920, 1040))
    floors = [s for s in compute_surfaces(WorldSnapshot(monitors=(left, right))) if s.owner is None]
    assert floors == [Segment(1040, 0, 3840, None)]


def test_floors_at_different_heights_stay_separate():
    left = Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080))
    right = Monitor(Rect(1920, 0, 1280, 1024), Rect(1920, 0, 1280, 1024))
    floors = [s for s in compute_surfaces(WorldSnapshot(monitors=(left, right))) if s.owner is None]
    assert len(floors) == 2
