import json

from felix.platform.base import CoordMapper, Monitor, Rect, WinRect, WorldSnapshot
from felix.platform.fake import FakeBackend, load_scene


def test_rect_edges():
    r = Rect(10, 20, 30, 40)
    assert (r.right, r.bottom) == (40, 60)
    assert r.contains(10, 20) and not r.contains(40, 20)


def test_mapper_is_identity_for_matching_layouts():
    m = CoordMapper([Rect(0, 0, 1920, 1080)], [Rect(0, 0, 1920, 1080)])
    assert m.point(100, 200) == (100, 200)
    assert m.rect(Rect(1, 2, 3, 4)) == Rect(1, 2, 3, 4)


def test_mapper_scales_physical_to_logical_pixels():
    m = CoordMapper([Rect(0, 0, 3840, 2160)], [Rect(0, 0, 1920, 1080)])
    assert m.point(100, 200) == (50, 100)
    assert m.rect(Rect(100, 200, 400, 300)) == Rect(50, 100, 200, 150)


def test_mapper_handles_mixed_dpi_monitors_side_by_side():
    native = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 3840, 2160)]
    logical = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1920, 1080)]
    m = CoordMapper(native, logical)
    assert m.point(1920 + 200, 100) == (1920 + 100, 50)
    assert m.point(500, 500) == (500, 500)


def test_mapper_pairs_monitors_by_layout_order_not_list_order():
    native = [Rect(1920, 0, 3840, 2160), Rect(0, 0, 1920, 1080)]
    logical = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1920, 1080)]
    assert CoordMapper(native, logical).point(1920 + 200, 100) == (1920 + 100, 50)


def test_mapper_uses_nearest_monitor_for_points_outside():
    m = CoordMapper([Rect(0, 0, 3840, 2160)], [Rect(0, 0, 1920, 1080)])
    assert m.point(-100, 0) == (-50, 0)


def test_mapper_maps_a_rect_through_the_monitor_holding_its_center():
    native = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 3840, 2160)]
    logical = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1920, 1080)]
    m = CoordMapper(native, logical)
    assert m.rect(Rect(1920 + 400, 400, 800, 600)) == Rect(1920 + 200, 200, 400, 300)


def test_fake_backend_serves_a_scene_loaded_from_json(tmp_path):
    scene = {
        "monitors": [{"geometry": [0, 0, 1920, 1080], "workarea": [0, 32, 1920, 1048]}],
        "windows": [{"id": 7, "rect": [100, 200, 800, 600]}, {"id": 3, "rect": [0, 0, 400, 300], "fullscreen": True}],
        "cursor": [5, 6],
    }
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(scene))
    snap = load_scene(path)
    assert snap == WorldSnapshot(
        monitors=(Monitor(Rect(0, 0, 1920, 1080), Rect(0, 32, 1920, 1048)),),
        windows=(WinRect(7, Rect(100, 200, 800, 600)), WinRect(3, Rect(0, 0, 400, 300), fullscreen=True)),
        cursor=(5, 6),
    )
    assert FakeBackend(snap).snapshot() is snap
