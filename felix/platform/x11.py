"""Backend X11 : fenêtres EWMH lues avec python-xlib dans un thread dédié.

Le thread produit un état « natif » (pixels X) ; snapshot(), appelé depuis le
thread Qt, le convertit en coordonnées logiques Qt et ajoute le curseur.
"""
import logging
import os
import select
import time

from Xlib import X, display, error
from Xlib.ext import randr

from felix.core.world import Rect, WinRect
from felix.platform.base import NativeState, PollingBackend, qt_logical_monitors
from felix.platform.x11_parse import frame_rect, is_candidate, workareas_for

log = logging.getLogger(__name__)

COALESCE = 0.033  # regroupe les rafales d'événements (déplacement d'une fenêtre à la souris…)
SAFETY = 2.0  # relecture de sécurité même sans événement
TOPLEVEL_EVENTS = (X.ConfigureNotify, X.MapNotify, X.UnmapNotify, X.DestroyNotify, X.CreateNotify,
                   X.ReparentNotify)


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

    def watch(self):
        """S'abonne aux changements de la racine : propriétés EWMH et fenêtres de premier niveau."""
        self.root.change_attributes(event_mask=X.PropertyChangeMask | X.SubstructureNotifyMask)
        self.d.flush()

    def drain(self):
        """Vide la file d'événements ; True si l'un d'eux concerne les fenêtres gérées."""
        relevant = False
        while self.d.pending_events():
            ev = self.d.next_event()
            if ev.type == X.PropertyNotify:
                relevant = True
            elif ev.type in TOPLEVEL_EVENTS and not getattr(ev, "override", False):
                relevant = True  # les fenêtres override-redirect (dont le chat) bougent sans cesse
        return relevant

    def wait_for_change(self, timeout, stop):
        deadline = time.monotonic() + timeout
        while not stop.is_set():
            if self.drain():
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            select.select([self.d.fileno()], [], [], min(remaining, 0.25))
        return False

    def close(self):
        self.d.close()


class X11Backend(PollingBackend):
    name = "x11"

    def __init__(self, display_name=None, interval=SAFETY, logical_monitors=qt_logical_monitors, cursor=True):
        super().__init__(interval, logical_monitors, cursor)
        self.reader = X11Reader(display_name)
        self.start()

    def _loop(self):
        """Relit l'état à chaque changement signalé par le serveur X, et au moins toutes les SAFETY s."""
        try:
            self.reader.watch()
            while not self._stop.is_set():
                self._read_once()
                if self.reader.wait_for_change(min(self.interval, SAFETY), self._stop):
                    self._stop.wait(COALESCE)
                    self.reader.drain()
        except Exception:
            log.exception("connexion X11 perdue : le chat garde un état minimal")
        finally:
            self.reader.close()

    def read_native(self):
        return self.reader.read()
