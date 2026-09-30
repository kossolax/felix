"""Intégration : un Xvfb privé où le test joue le rôle du gestionnaire de fenêtres."""
import os
import shutil
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("Xvfb"),
                                reason="Xvfb requis")

from felix.core.world import Rect  # noqa: E402


@pytest.fixture
def xserver():
    from Xlib import display
    read_fd, write_fd = os.pipe()
    proc = subprocess.Popen(["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "1600x900x24", "-nolisten", "tcp"],
                            pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(write_fd)
    with os.fdopen(read_fd) as pipe:
        number = pipe.readline().strip()  # Xvfb choisit lui-même un numéro libre
    if not number:
        proc.kill()
        pytest.skip("Xvfb n'a pas démarré")
    name = f":{number}"
    d = display.Display(name)
    yield name, d
    d.close()
    proc.terminate()  # arrêt propre : Xvfb supprime son socket et son verrou
    proc.wait(timeout=5)


def make_window(d, x, y, w, h, **props):
    from Xlib import X, Xatom
    root = d.screen().root
    win = root.create_window(x, y, w, h, 0, d.screen().root_depth, X.InputOutput, X.CopyFromParent)
    for name, (kind, values) in props.items():
        atom_type = {"atom": Xatom.ATOM, "card": Xatom.CARDINAL}[kind]
        if kind == "atom":
            values = [d.intern_atom(v) for v in values]
        win.change_property(d.intern_atom(name), atom_type, 32, values)
    win.map()
    return win


def set_root(d, name, kind, values):
    from Xlib import Xatom
    atom_type = {"window": Xatom.WINDOW, "card": Xatom.CARDINAL}[kind]
    d.screen().root.change_property(d.intern_atom(name), atom_type, 32, values)


def test_reader_lists_candidate_windows_top_down_with_visible_frames(xserver):
    from felix.platform.x11 import X11Reader
    name, d = xserver
    bottom = make_window(d, 100, 130, 400, 300, _NET_FRAME_EXTENTS=("card", [0, 0, 30, 0]),
                         _NET_WM_WINDOW_TYPE=("atom", ["_NET_WM_WINDOW_TYPE_NORMAL"]))
    csd = make_window(d, 480, 280, 440, 346, _GTK_FRAME_EXTENTS=("card", [20, 20, 20, 26]))
    desk = make_window(d, 0, 0, 1600, 900, _NET_WM_WINDOW_TYPE=("atom", ["_NET_WM_WINDOW_TYPE_DESKTOP"]))
    other_ws = make_window(d, 10, 10, 100, 100, _NET_WM_DESKTOP=("card", [3]))
    full = make_window(d, 0, 0, 1600, 900, _NET_WM_STATE=("atom", ["_NET_WM_STATE_FULLSCREEN"]))
    mine = make_window(d, 50, 50, 60, 60, _NET_WM_PID=("card", [os.getpid()]))
    set_root(d, "_NET_CLIENT_LIST_STACKING", "window",
             [desk.id, bottom.id, other_ws.id, csd.id, mine.id, full.id])  # du bas vers le haut
    set_root(d, "_NET_CURRENT_DESKTOP", "card", [0])
    set_root(d, "_GTK_WORKAREAS_D0", "card", [0, 32, 1600, 868])
    d.sync()

    native = X11Reader(name).read()
    assert native.monitors == [Rect(0, 0, 1600, 900)]
    assert native.workareas == [Rect(0, 32, 1600, 868)]
    assert [(w.id, w.rect, w.fullscreen) for w in native.windows] == [
        (full.id, Rect(0, 0, 1600, 900), True),
        (csd.id, Rect(500, 300, 400, 300), False),
        (bottom.id, Rect(100, 100, 400, 330), False),
    ]


def test_wait_ready_returns_once_the_first_read_is_done(xserver, qapp):
    from felix.platform.x11 import X11Backend
    name, d = xserver
    win = make_window(d, 200, 300, 400, 200)
    set_root(d, "_NET_CLIENT_LIST_STACKING", "window", [win.id])
    d.sync()
    backend = X11Backend(name, interval=5, logical_monitors=lambda: [Rect(0, 0, 1600, 900)])
    try:
        assert backend.wait_ready(2)
        assert backend.snapshot().windows[0].rect == Rect(200, 300, 400, 200)
    finally:
        backend.stop()


def test_backend_maps_native_state_to_a_snapshot(xserver, qapp):
    from felix.platform.x11 import X11Backend
    name, d = xserver
    win = make_window(d, 200, 300, 400, 200)
    set_root(d, "_NET_CLIENT_LIST_STACKING", "window", [win.id])
    set_root(d, "_NET_WORKAREA", "card", [0, 0, 1600, 900])
    d.sync()
    backend = X11Backend(name, interval=0.05, logical_monitors=lambda: [Rect(0, 0, 800, 450)])
    try:
        for _ in range(40):
            snap = backend.snapshot()
            if snap.windows:
                break
            time.sleep(0.05)
        # écran natif 1600×900 vu par Qt en 800×450 : tout est divisé par 2
        assert snap.windows[0].rect == Rect(100, 150, 200, 100)
        assert snap.monitors[0].geometry == Rect(0, 0, 800, 450)
    finally:
        backend.stop()
