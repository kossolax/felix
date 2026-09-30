"""Backend Windows 10/11 : EnumWindows + DWM via ctypes, lu dans un thread.

Qt active la gestion DPI « par moniteur v2 » à la création de QApplication :
ce backend doit donc être créé après, et reçoit des pixels physiques que
PollingBackend convertit en coordonnées logiques Qt.
"""
import ctypes
import os
from ctypes import wintypes as wt

from felix.core.world import Rect
from felix.platform.base import NativeState, PollingBackend, qt_logical_monitors
from felix.platform.windows_parse import WinInfo, filter_windows

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GWL_EXSTYLE = -20
HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
MonitorEnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
user32.EnumDisplayMonitors.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), MonitorEnumProc, wt.LPARAM]
user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]


def _rect(r):
    return Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)


def monitors():
    out = []

    def callback(hmon, _hdc, _rect_ptr, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            out.append((_rect(info.rcMonitor), _rect(info.rcWork)))
        return True

    user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
    return sorted(out, key=lambda m: (m[0].x, m[0].y))


def window_infos():
    handles = []
    user32.EnumWindows(EnumWindowsProc(lambda hwnd, _: handles.append(hwnd) or True), 0)
    infos = []
    for hwnd in handles:  # du haut vers le bas
        if not user32.IsWindowVisible(hwnd):
            continue
        cloaked = wt.DWORD(0)
        dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        rect = wt.RECT()
        if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)):
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
        pid = wt.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        infos.append(WinInfo(
            hwnd=hwnd, rect=_rect(rect), pid=pid.value, cls=cls.value,
            exstyle=user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF,
            visible=True, iconic=bool(user32.IsIconic(hwnd)), cloaked=bool(cloaked.value)))
    return infos


def keep_on_top(hwnd):
    """La barre des tâches repasse devant quand on clique dessus : on réaffirme TOPMOST."""
    user32.SetWindowPos(wt.HWND(hwnd), HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


class WindowsBackend(PollingBackend):
    name = "windows"

    def __init__(self, interval=0.2, logical_monitors=qt_logical_monitors, cursor=True):
        super().__init__(interval, logical_monitors, cursor)
        self.own_pid = os.getpid()
        self.start()

    def read_native(self):
        mons = monitors()
        geoms = [g for g, _ in mons]
        return NativeState(geoms, [w for _, w in mons], filter_windows(window_infos(), self.own_pid, geoms))
