"""Filtrage des fenêtres Win32 (sans ctypes, testable partout)."""
from dataclasses import dataclass

from felix.core.world import Rect, WinRect

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_TRANSPARENT = 0x00000020

SHELL_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "XamlExplorerHostIslandWindow", "Windows.UI.Core.CoreWindow",
}
MIN_W, MIN_H = 50, 30


@dataclass(frozen=True)
class WinInfo:
    hwnd: int
    rect: Rect  # DWMWA_EXTENDED_FRAME_BOUNDS, px physiques
    pid: int
    cls: str
    exstyle: int
    visible: bool
    iconic: bool
    cloaked: bool


def _covers(rect, monitor):
    return (rect.x <= monitor.x and rect.y <= monitor.y
            and rect.right >= monitor.right and rect.bottom >= monitor.bottom)


def filter_windows(infos, own_pid, monitors):
    """infos dans l'ordre d'EnumWindows (du haut vers le bas)."""
    out = []
    for w in infos:
        if not w.visible or w.iconic or w.cloaked or w.pid == own_pid or w.cls in SHELL_CLASSES:
            continue
        if w.exstyle & WS_EX_TRANSPARENT:
            continue
        if w.exstyle & WS_EX_TOOLWINDOW and not w.exstyle & WS_EX_APPWINDOW:
            continue
        if w.rect.w < MIN_W or w.rect.h < MIN_H:
            continue
        out.append(WinRect(w.hwnd, w.rect, any(_covers(w.rect, m) for m in monitors)))
    return out
