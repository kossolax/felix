"""Backend X11 : fenêtres EWMH lues avec python-xlib dans un thread dédié.

Le thread produit un état « natif » (pixels X) ; snapshot(), appelé depuis le
thread Qt, le convertit en coordonnées logiques Qt et ajoute le curseur.
"""
import logging
import os
import threading
from dataclasses import dataclass

from Xlib import X, display, error
from Xlib.ext import randr

from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
from felix.platform.base import CoordMapper
from felix.platform.x11_parse import frame_rect, is_candidate, workareas_for

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NativeState:
    monitors: list
    workareas: list
    windows: list  # WinRect natifs, du haut vers le bas


class X11Reader:
    def __init__(self, display_name=None):
        self.d = display.Display(display_name)
        self.root = self.d.screen().root
        self.own_pid = os.getpid()
        self._atoms = {}
        self._names = {}

    def atom(self, name):
        if name not in self._atoms:
            self._atoms[name] = self.d.intern_atom(name)
        return self._atoms[name]

    def atom_name(self, atom):
        if atom not in self._names:
            self._names[atom] = self.d.get_atom_name(atom)
        return self._names[atom]

    def prop(self, win, name):
        reply = win.get_full_property(self.atom(name), X.AnyPropertyType)
        return list(reply.value) if reply is not None else None

    def monitors(self):
        try:
            reply = randr.get_monitors(self.root, is_active=True)
            mons = [Rect(m.x, m.y, m.width_in_pixels, m.height_in_pixels) for m in reply.monitors]
            if mons:
                return sorted(mons, key=lambda r: (r.x, r.y))
        except Exception:  # RandR < 1.5
            pass
        g = self.root.get_geometry()
        return [Rect(0, 0, g.width, g.height)]

    def _window(self, wid, current_desktop):
        win = self.d.create_resource_object("window", wid)
        pid = self.prop(win, "_NET_WM_PID")
        if pid and pid[0] == self.own_pid:
            return None
        types = [self.atom_name(a) for a in self.prop(win, "_NET_WM_WINDOW_TYPE") or []]
        states = [self.atom_name(a) for a in self.prop(win, "_NET_WM_STATE") or []]
        desktop = self.prop(win, "_NET_WM_DESKTOP")
        if not is_candidate(types, states, desktop[0] if desktop else None, current_desktop):
            return None
        geom = win.get_geometry()
        pos = self.root.translate_coords(win, 0, 0)
        rect = frame_rect(pos.x, pos.y, geom.width, geom.height,
                          self.prop(win, "_NET_FRAME_EXTENTS"), self.prop(win, "_GTK_FRAME_EXTENTS"))
        return WinRect(wid, rect, "_NET_WM_STATE_FULLSCREEN" in states)

    def read(self):
        monitors = self.monitors()
        current = (self.prop(self.root, "_NET_CURRENT_DESKTOP") or [0])[0]
        values = self.prop(self.root, f"_GTK_WORKAREAS_D{current}")
        if not values:
            net = self.prop(self.root, "_NET_WORKAREA") or []
            values = net[4 * current:4 * current + 4]
        stacking = self.prop(self.root, "_NET_CLIENT_LIST_STACKING") or self.prop(self.root, "_NET_CLIENT_LIST") or []
        windows = []
        for wid in reversed(stacking):
            try:
                w = self._window(wid, current)
            except (error.BadWindow, error.BadDrawable, error.BadMatch):
                continue  # fermée pendant la lecture
            if w is not None and w.rect.w > 0 and w.rect.h > 0:
                windows.append(w)
        return NativeState(monitors, workareas_for(values, monitors), windows)

    def close(self):
        self.d.close()


def _qt_logical_monitors():
    from PySide6.QtGui import QGuiApplication
    return [Rect(s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height())
            for s in QGuiApplication.screens()]


class X11Backend:
    name = "x11"

    def __init__(self, display_name=None, interval=0.2, logical_monitors=_qt_logical_monitors, cursor=True):
        self.reader = X11Reader(display_name)
        self.interval = interval
        self._logical_monitors = logical_monitors
        self._cursor = cursor
        self._native = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="felix-x11", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._native = self.reader.read()
                self._ready.set()
            except Exception:
                log.exception("lecture X11")
            self._stop.wait(self.interval)
        self.reader.close()

    def wait_ready(self, timeout=2.0):
        return self._ready.wait(timeout)

    def snapshot(self):
        cursor = None
        if self._cursor:
            from PySide6.QtGui import QCursor
            pos = QCursor.pos()
            cursor = (pos.x(), pos.y())
        native = self._native
        if native is None:
            from felix.platform.degraded import qt_monitors
            return WorldSnapshot(monitors=qt_monitors(), cursor=cursor)
        logical = self._logical_monitors()
        mapper = CoordMapper(native.monitors, logical if len(logical) == len(native.monitors) else native.monitors)
        return WorldSnapshot(
            monitors=tuple(Monitor(mapper.rect(g), mapper.rect(wa)) for g, wa in zip(native.monitors, native.workareas)),
            windows=tuple(WinRect(w.id, mapper.rect(w.rect), w.fullscreen) for w in native.windows),
            cursor=cursor,
        )

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
