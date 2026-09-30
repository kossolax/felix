import json

from felix.core.world import Rect, WinRect
from felix.platform.gnome_shell import parse_state


def test_parse_state_reads_monitors_workareas_and_windows_top_down():
    payload = json.dumps({
        "monitors": [
            {"geometry": [0, 0, 1920, 1080], "workarea": [0, 32, 1920, 1048], "scale": 1},
            {"geometry": [1920, 0, 1280, 1024], "workarea": [1920, 32, 1280, 992], "scale": 1},
        ],
        "windows": [
            {"id": 12, "rect": [100, 200, 800, 600], "fullscreen": False},
            {"id": 3, "rect": [0, 0, 1920, 1080], "fullscreen": True},
        ],
    })
    state = parse_state(payload)
    assert state.monitors == [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1280, 1024)]
    assert state.workareas == [Rect(0, 32, 1920, 1048), Rect(1920, 32, 1280, 992)]
    assert state.windows == [WinRect(12, Rect(100, 200, 800, 600)), WinRect(3, Rect(0, 0, 1920, 1080), True)]


def test_parse_state_sorts_monitors_in_layout_order():
    payload = json.dumps({"monitors": [
        {"geometry": [1920, 0, 1280, 1024], "workarea": [1920, 0, 1280, 1024]},
        {"geometry": [0, 0, 1920, 1080], "workarea": [0, 0, 1920, 1080]},
    ], "windows": []})
    assert parse_state(payload).monitors == [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1280, 1024)]
