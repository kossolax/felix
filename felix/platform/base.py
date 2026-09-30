"""Interface commune des backends de plateforme."""
import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot

__all__ = ["Backend", "CoordMapper", "Monitor", "NativeState", "PollingBackend", "Rect", "WinRect",
           "WorldSnapshot"]

log = logging.getLogger(__name__)


class Backend(Protocol):
    name: str

    def snapshot(self) -> WorldSnapshot:
        """Dernier état connu (non bloquant), en coordonnées logiques Qt."""

    def stop(self) -> None:
        ...


def _layout_key(r):
    return (r.x, r.y)


class CoordMapper:
    """Convertit des coordonnées natives (px physiques, écran X…) en coordonnées logiques Qt.

    Les moniteurs natifs et Qt sont appariés dans l'ordre de disposition (x, puis y).
    """

    def __init__(self, native, logical):
        if len(native) != len(logical):
            raise ValueError("nombre de moniteurs différent entre natif et Qt")
        self.pairs = list(zip(sorted(native, key=_layout_key), sorted(logical, key=_layout_key)))

    def _pair_for(self, px, py):
        for nat, log in self.pairs:
            if nat.contains(px, py):
                return nat, log
        return min(self.pairs, key=lambda p: p[0].distance2(px, py))

    @staticmethod
    def _map(nat, log, px, py):
        sx, sy = log.w / nat.w, log.h / nat.h
        return log.x + (px - nat.x) * sx, log.y + (py - nat.y) * sy

    def point(self, px, py):
        x, y = self._map(*self._pair_for(px, py), px, py)
        return round(x), round(y)

    def rect(self, r):
        nat, lgc = self._pair_for(*r.center)
        x0, y0 = self._map(nat, lgc, r.x, r.y)
        x1, y1 = self._map(nat, lgc, r.right, r.bottom)
        return Rect(round(x0), round(y0), round(x1) - round(x0), round(y1) - round(y0))


@dataclass(frozen=True)
class NativeState:
    """État lu par un backend, en coordonnées natives (px physiques, écran X…)."""
    monitors: list
    workareas: list
    windows: list  # WinRect natifs, du haut vers le bas


def qt_logical_monitors():
    from PySide6.QtGui import QGuiApplication
    return [Rect(s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height())
            for s in QGuiApplication.screens()]


class PollingBackend:
    """Lit l'état natif dans un thread (read_native), le convertit en coordonnées Qt dans snapshot()."""
    name = "polling"

    def __init__(self, interval=0.2, logical_monitors=qt_logical_monitors, cursor=True, stale_after=3.0):
        self.interval = interval
        self._logical_monitors = logical_monitors
        self._cursor = cursor
        self.stale_after = stale_after  # sans lecture réussie depuis ce délai : état minimal
        self._native = None
        self._last_ok = None
        self._failing = False
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name=f"felix-{self.name}", daemon=True)

    def start(self):
        self._thread.start()
        return self

    def read_native(self):
        raise NotImplementedError

    def close_native(self):
        pass

    def _read_once(self):
        """Une lecture ; les échecs sont journalisés une fois par série, pas à chaque tour."""
        try:
            self._native = self.read_native()
        except Exception:
            if not self._failing:
                log.warning("lecture %s impossible (état minimal en attendant)", self.name, exc_info=True)
                self._failing = True
            return
        if self._failing:
            log.info("lecture %s rétablie", self.name)
            self._failing = False
        self._last_ok = time.monotonic()
        self._ready.set()

    def _stale(self):
        return self._last_ok is None or time.monotonic() - self._last_ok > self.stale_after

    def _loop(self):
        while not self._stop.is_set():
            self._read_once()
            self._stop.wait(self.interval)
        self.close_native()

    def wait_ready(self, timeout=2.0):
        return self._ready.wait(timeout)

    def snapshot(self):
        cursor = None
        if self._cursor:
            from PySide6.QtGui import QCursor
            pos = QCursor.pos()
            cursor = (pos.x(), pos.y())
        native = self._native
        if native is None or self._stale():
            from felix.platform.degraded import qt_monitors
            return WorldSnapshot(monitors=qt_monitors(), cursor=cursor)
        logical = self._logical_monitors()
        mapper = CoordMapper(native.monitors, logical if len(logical) == len(native.monitors) else native.monitors)
        return WorldSnapshot(
            monitors=tuple(Monitor(mapper.rect(g), mapper.rect(wa))
                           for g, wa in zip(native.monitors, native.workareas)),
            windows=tuple(WinRect(w.id, mapper.rect(w.rect), w.fullscreen) for w in native.windows),
            cursor=cursor,
        )

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
