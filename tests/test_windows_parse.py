from felix.core.world import Rect, WinRect
from felix.platform.windows_parse import (WS_CAPTION, WS_EX_APPWINDOW, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT,
                                          WinInfo, filter_windows)

MONITORS = [Rect(0, 0, 1920, 1080)]


def info(hwnd, rect, **kw):
    defaults = dict(pid=100, cls="Notepad", style=0, exstyle=0, visible=True, iconic=False, cloaked=False)
    defaults.update(kw)
    return WinInfo(hwnd=hwnd, rect=rect, **defaults)


def test_keeps_visible_application_windows_in_z_order():
    infos = [info(1, Rect(10, 10, 500, 400)), info(2, Rect(100, 100, 300, 200))]
    assert filter_windows(infos, own_pid=1, monitors=MONITORS) == [
        WinRect(1, Rect(10, 10, 500, 400)), WinRect(2, Rect(100, 100, 300, 200))]


def test_drops_hidden_minimized_cloaked_and_own_windows():
    infos = [
        info(1, Rect(0, 0, 400, 300), visible=False),
        info(2, Rect(0, 0, 400, 300), iconic=True),
        info(3, Rect(0, 0, 400, 300), cloaked=True),
        info(4, Rect(0, 0, 400, 300), pid=42),
    ]
    assert filter_windows(infos, own_pid=42, monitors=MONITORS) == []


def test_drops_tool_windows_unless_they_are_app_windows():
    infos = [
        info(1, Rect(0, 0, 400, 300), exstyle=WS_EX_TOOLWINDOW),
        info(2, Rect(0, 0, 400, 300), exstyle=WS_EX_TOOLWINDOW | WS_EX_APPWINDOW),
        info(3, Rect(0, 0, 400, 300), exstyle=WS_EX_TRANSPARENT),
    ]
    assert [w.id for w in filter_windows(infos, own_pid=1, monitors=MONITORS)] == [2]


def test_drops_shell_windows_and_tiny_rects():
    infos = [info(i, Rect(0, 0, 1920, 1080), cls=c) for i, c in enumerate(
        ["Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
         "XamlExplorerHostIslandWindow", "Windows.UI.Core.CoreWindow"])]
    infos.append(info(99, Rect(5, 5, 20, 10)))
    assert filter_windows(infos, own_pid=1, monitors=MONITORS) == []


def test_window_covering_a_whole_monitor_is_fullscreen():
    infos = [info(1, Rect(0, 0, 1920, 1080)), info(2, Rect(0, 0, 1920, 1040))]
    out = filter_windows(infos, own_pid=1, monitors=MONITORS)
    assert [(w.id, w.fullscreen) for w in out] == [(1, True), (2, False)]


def test_a_maximized_window_with_a_title_bar_is_not_fullscreen():
    # barre des tâches masquée automatiquement : la fenêtre maximisée couvre tout l'écran
    infos = [info(1, Rect(0, 0, 1920, 1080), style=WS_CAPTION)]
    assert filter_windows(infos, own_pid=1, monitors=MONITORS)[0].fullscreen is False
