"""Interface commune des backends de plateforme."""
from typing import Protocol

from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot

__all__ = ["Backend", "CoordMapper", "Monitor", "Rect", "WinRect", "WorldSnapshot"]


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
        nat, log = self._pair_for(*r.center)
        x0, y0 = self._map(nat, log, r.x, r.y)
        x1, y1 = self._map(nat, log, r.right, r.bottom)
        return Rect(round(x0), round(y0), round(x1) - round(x0), round(y1) - round(y0))
