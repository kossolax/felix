"""Ce que le chat sait du bureau à un instant donné (coordonnées logiques Qt)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    @property
    def center(self):
        return (self.x + self.w / 2, self.y + self.h / 2)

    def contains(self, px, py):
        return self.x <= px < self.right and self.y <= py < self.bottom

    def distance2(self, px, py):
        dx = max(self.x - px, 0, px - (self.right - 1))
        dy = max(self.y - py, 0, py - (self.bottom - 1))
        return dx * dx + dy * dy


@dataclass(frozen=True)
class Monitor:
    geometry: Rect
    workarea: Rect


@dataclass(frozen=True)
class WinRect:
    id: int
    rect: Rect
    fullscreen: bool = False


@dataclass(frozen=True)
class WorldSnapshot:
    monitors: tuple = ()
    windows: tuple = ()  # du haut vers le bas de la pile
    cursor: tuple = None  # (x, y) ou None si inconnu
