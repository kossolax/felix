"""Balle libre (pelote de laine, ballon de plage) : elle roule sur le sol et le haut des
fenêtres, rebondit et tombe.

Sa position (x, y) est son point de contact, comme les pieds du chat. Le bord d'un écran et
une fenêtre placée devant l'arrêtent ; le vrai bord d'une fenêtre la laisse tomber.
"""
import math
from dataclasses import dataclass

from felix.core.physics import GRAVITY, MAX_FALL_SPEED, follow_support
from felix.core.surfaces import landing_between, support_at

BALL_RADIUS = 13
BALL_FRICTION = 300.0  # px/s² : décélération en roulant
BALL_BOUNCE = 0.45  # part de la vitesse gardée à chaque rebond au sol
BALL_MIN_BOUNCE = 140.0  # px/s : en dessous, elle se pose
WALL_BOUNCE = 0.6
AIR_SPIN_LOSS = 0.85  # vitesse horizontale gardée à chaque rebond
ROLL_STEP = 20  # px roulés par image de la planche (4 images par tour)
FRAMES = 4
MAX_THROW = 2500.0


@dataclass(frozen=True)
class BallKind:
    anim: str  # images (une par quart de tour)
    radius: int
    roll_step: int  # px roulés par image
    friction: float  # px/s² en roulant
    bounce: float  # part de la vitesse gardée à chaque rebond au sol
    at_feet: int  # px entre les pieds du chat assis et la balle que dessinent ses images
    scene: str  # jeu du chat avec elle (None : il ne la reprend pas de lui-même)
    frames: int = FRAMES
    anim_left: str = None  # images vers la gauche, pour un jouet qui marche (sinon : il roule)
    grabbable: bool = True
    speed: float = 0.0  # px/s d'un jouet qui marche


YARN = BallKind("yarn_ball", BALL_RADIUS, ROLL_STEP, BALL_FRICTION, BALL_BOUNCE, 38, "yarn")
BEACH = BallKind("beach_ball", 32, 50, 60.0, 0.6, 56, "beachball")  # extension Fun and Games
MOUSE = BallKind("mouse_walk_right", 27, 6, 0.0, 0.0, 0, None, frames=7, anim_left="mouse_walk_left",
                 grabbable=False, speed=60.0)  # souris mécanique : elle marche droit devant elle, la clé tourne


def _window_rect(snap, wid):
    win = next((w for w in snap.windows if w.id == wid), None)
    return win.rect if win else None


class Ball:
    def __init__(self, x, y, scale=1, home=None, kind=YARN):
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.support = None
        self.owner_rect = None
        self.k = scale
        self.home = home  # "box" si elle sort de la boîte à jouets
        self.held = False
        self.exits = False  # renvoyée pour de bon : plus de murs ni de frottement
        self.gone = False
        self.roll = 0.0  # distance roulée (signée), pour l'image
        self.heading = 1  # sens de la marche (jouets qui marchent)

    @property
    def frame(self):
        return int(self.roll // (self.kind.roll_step * self.k)) % self.kind.frames

    @property
    def anim(self):
        return self.kind.anim_left if self.kind.anim_left and self.heading < 0 else self.kind.anim

    def _advance(self, dx):
        if self.kind.anim_left:  # un jouet qui marche : ses images avancent dans les deux sens
            if dx:
                self.heading = 1 if dx > 0 else -1
            self.roll += abs(dx)
        else:
            self.roll += dx

    @property
    def grounded(self):
        return self.support is not None

    @property
    def resting(self):
        return self.support is not None and self.vx == 0 and not self.held

    def kick(self, vx, vy=0.0):
        self.vx, self.vy = float(vx), float(vy)
        if vx:
            self.heading = 1 if vx > 0 else -1
        if vy < 0:
            self.support = self.owner_rect = None

    def leave(self, scale=1):
        """Un jouet qui marche s'en va tout droit, jusqu'à sortir de l'écran."""
        self.exits = True
        self.kick(self.heading * self.kind.speed * scale, 0.0)

    def grab(self):
        self.held = True
        self.support = self.owner_rect = None
        self.vx = self.vy = 0.0

    def move_to(self, x, y):
        self.x, self.y = float(x), float(y)

    def throw(self, vx, vy):
        self.held = False
        speed = math.hypot(vx, vy)
        limit = MAX_THROW * self.k
        if speed > limit:
            vx, vy = vx * limit / speed, vy * limit / speed
        self.vx, self.vy = float(vx), float(vy)

    def update(self, dt, snap, segs):
        if self.held or self.gone:
            return
        if self.support is not None:
            follow_support(self, snap, segs)
            if self.support is None:
                self.vy = 0.0
        if self.support is not None:
            self._roll(dt, snap, segs)
        else:
            self._fly(dt, snap, segs)
        if self.exits and snap.monitors:
            r = self.kind.radius * self.k
            left, top, right, bottom = _bounds(snap)
            self.gone = not (left - r <= self.x <= right + r and self.y <= bottom + 2 * r)

    def _roll(self, dt, snap, segs):
        if self.vx == 0:
            return
        dx = self.vx * dt
        self.x += dx
        self._advance(dx)
        if not self.exits:
            dv = self.kind.friction * self.k * dt
            self.vx = 0.0 if abs(self.vx) <= dv else self.vx - math.copysign(dv, self.vx)
        seg = self.support
        r = self.kind.radius * self.k
        walls = not self.exits
        lo = seg.x0 + r if walls and self._wall(seg, -1, snap) else seg.x0
        hi = seg.x1 - r if walls and self._wall(seg, 1, snap) else seg.x1
        if lo <= self.x < hi:
            return
        side = -1 if self.x < lo else 1
        if (side < 0 and lo > seg.x0) or (side > 0 and hi < seg.x1):  # mur : elle repart dans l'autre sens
            self.x = lo if side < 0 else hi - 0.01
            self.vx = -self.vx * WALL_BOUNCE
            return
        nxt = support_at(segs, self.x, seg.y)
        if nxt is not None:  # une autre surface prend le relais à la même hauteur
            self.support = nxt
            self.owner_rect = _window_rect(snap, nxt.owner) if nxt.owner is not None else None
            return
        self.support = self.owner_rect = None  # bord de fenêtre : elle tombe
        self.vy = 0.0

    def _wall(self, seg, side, snap):
        edge = seg.x0 if side < 0 else seg.x1
        if seg.owner is None:  # bord d'écran, sauf si un autre écran continue là
            return not any(m.geometry.contains(edge + side, seg.y - 1) for m in snap.monitors)
        rect = _window_rect(snap, seg.owner)
        return rect is not None and rect.x < edge < rect.right  # bord caché par une fenêtre devant

    def _fly(self, dt, snap, segs):
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL_SPEED)
        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        self._advance(self.vx * dt)
        if not self.exits and snap.monitors:
            r = self.kind.radius * self.k
            left, top, right, _bottom = _bounds(snap)
            if nx < left + r:
                nx, self.vx = left + r, abs(self.vx) * WALL_BOUNCE
            elif nx > right - r:
                nx, self.vx = right - r, -abs(self.vx) * WALL_BOUNCE
            if ny - 2 * r < top and self.vy < 0:
                ny, self.vy = top + 2 * r, -self.vy * WALL_BOUNCE
        if self.vy > 0:
            seg = landing_between(segs, nx, self.y, ny)
            if seg is not None:
                self.x, self.y = nx, seg.y
                if self.vy > BALL_MIN_BOUNCE:
                    self.vy = -self.vy * self.kind.bounce
                    self.vx *= AIR_SPIN_LOSS
                else:
                    self.vy = 0.0
                    self.support = seg
                    self.owner_rect = _window_rect(snap, seg.owner) if seg.owner is not None else None
                return
        self.x, self.y = nx, ny
        if self.exits:
            return
        floors = [s for s in segs if s.owner is None]
        if floors and self.y > max(s.y for s in floors):  # passée sous tout : retour au sol le plus proche
            floor = min(floors, key=lambda s: abs((s.x0 + s.x1) / 2 - self.x))
            self.x = min(max(self.x, floor.x0), floor.x1 - 1)
            self.y, self.vy, self.support, self.owner_rect = floor.y, 0.0, floor, None


def _bounds(snap):
    geos = [m.geometry for m in snap.monitors]
    return (min(g.x for g in geos), min(g.y for g in geos), max(g.right for g in geos), max(g.bottom for g in geos))
