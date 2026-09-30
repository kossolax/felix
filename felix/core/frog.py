"""Grenouille de l'extension Fun and Games : elle n'avance qu'en sautant, un saut à la fois.

Même interface que les balles (Ball), pour prendre leur place à côté du chat : position = point
de contact, update(), frame et anim pour l'affichage.
"""
import random

from felix.core.ball import BallKind, _bounds
from felix.core.physics import step
from felix.core.tuning import FROG_HOP, FROG_HOP_FPS

FROG = BallKind("frog_sit_right", 20, 1, 0.0, 0.0, 0, None, grabbable=False)
SIT_FPS = 3


class Frog:
    kind = FROG
    home = None
    held = False

    def __init__(self, x, y, heading=1, scale=1, rng=None):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.support = self.owner_rect = None
        self.k = scale
        self.heading = heading  # 1 : tournée vers la droite
        self.exits = False  # s'en va pour de bon : saute jusqu'à sortir de l'écran
        self.gone = False
        self._hops = 0  # sauts encore à faire
        self._pause = (0.0, 0.0)
        self._hop_t = None  # temps écoulé dans le saut en cours
        self._x0 = self.x
        self._sit_t = 0.0
        self._wait = 0.0
        self.rng = rng or random.Random()

    @property
    def grounded(self):
        return self.support is not None

    @property
    def hopping(self):
        return self._hop_t is not None

    @property
    def resting(self):
        return self.grounded and not self.hopping and self._hops == 0

    @property
    def anim(self):
        side = "right" if self.heading > 0 else "left"
        return f"frog_hop_{side}" if self.hopping else f"frog_sit_{side}"

    @property
    def frame(self):
        if self.hopping:
            return min(int(self._hop_t * FROG_HOP_FPS), len(FROG_HOP) - 1)
        return int(self._sit_t * SIT_FPS) % 3

    def hop(self, count, heading=None, pause=(0.0, 0.0)):
        """`count` sauts vers `heading` (sa direction actuelle par défaut), posée `pause` s entre deux."""
        if heading is not None and not self.hopping:
            self.heading = heading
        self._hops, self._pause = count, pause
        self._wait = 0.0

    def stop(self):
        self._hops = 0

    def leave(self, _scale=1):
        """S'en va tout droit, saut après saut, jusqu'à sortir de l'écran."""
        self.exits = True
        self.hop(10 ** 6, pause=(0.2, 0.2))

    def update(self, dt, snap, segs):
        if self.gone:
            return
        step(self, dt, snap, segs)  # suit sa fenêtre, ou tombe
        if self.support is None:
            return
        if self.hopping:
            self._hop_t += dt
            i = min(int(self._hop_t * FROG_HOP_FPS), len(FROG_HOP) - 1)
            self.x = self._x0 + self.heading * FROG_HOP[i] * self.k
            if self._hop_t * FROG_HOP_FPS >= len(FROG_HOP):
                self._hop_t = None
                self._sit_t = 0.0
                self._wait = self.rng.uniform(*self._pause)
            if not self.support.spans(self.x):
                self.support = None  # au bout de sa surface : elle tombe
                self.vx = self.vy = 0.0
        else:
            self._sit_t += dt
            self._wait -= dt
            if self._hops > 0 and self._wait <= 0:
                self._hops -= 1
                self._hop_t, self._x0 = 0.0, self.x
        if self.exits and snap.monitors:
            left, _top, right, _bottom = _bounds(snap)
            self.gone = not (left - 40 * self.k <= self.x <= right + 40 * self.k)
