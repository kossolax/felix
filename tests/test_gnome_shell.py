import json

import pytest

pytest.importorskip("jeepney")  # backend réservé à Linux (dépendance jeepney)

from felix.core.world import Rect, WinRect  # noqa: E402
from felix.platform.gnome_shell import parse_state  # noqa: E402


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


class Reply:
    def __init__(self, body, error=False):
        from jeepney import MessageType
        self.body = body
        self.header = type("H", (), {"message_type": MessageType.error if error else MessageType.method_return})()


class FakeConn:
    """Bus de session factice : l'extension répond, puis disparaît (écran verrouillé)."""

    def __init__(self):
        self.gone = False

    def send_and_get_reply(self, msg, timeout=None):
        if self.gone:
            return Reply(("The name io.github.felix.Helper was not provided by any .service files",), error=True)
        if msg.header.fields[3] == "GetPointer":  # 3 = MEMBER
            return Reply((400, 300))
        return Reply((json.dumps({"monitors": [{"geometry": [0, 0, 1600, 900], "workarea": [0, 0, 1600, 900]}],
                                  "windows": [{"id": 1, "rect": [10, 20, 300, 200]}]}),))

    def close(self):
        pass


def test_backend_survives_the_extension_disappearing(qapp):
    import time
    from felix.platform import gnome_shell
    conn = FakeConn()
    backend = gnome_shell.GnomeShellBackend(interval=0.02, logical_monitors=lambda: [Rect(0, 0, 1600, 900)],
                                           connect=lambda: conn, stale_after=0.2)
    try:
        assert backend.wait_ready(2)
        time.sleep(0.1)
        snap = backend.snapshot()
        assert snap.cursor == (400, 300) and snap.windows[0].id == 1
        conn.gone = True
        time.sleep(0.4)
        snap = backend.snapshot()  # ne doit pas lever
        assert snap.cursor is None and snap.windows == ()
        conn.gone = False
        time.sleep(0.2)
        assert backend.snapshot().cursor == (400, 300)  # l'extension revient : tout repart
    finally:
        backend.stop()
