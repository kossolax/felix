"""Gravité, atterrissage, et suivi de la fenêtre qui porte le chat."""
from dataclasses import dataclass

from felix.core.surfaces import Segment, landing_between, support_at

GRAVITY = 2200.0  # px/s²
MAX_FALL_SPEED = 1600.0


@dataclass
class Body:
    x: float
    y: float  # position des pieds
    vx: float = 0.0
    vy: float = 0.0
    support: Segment = None
    owner_rect: object = None  # dernier Rect connu de la fenêtre porteuse

    @property
    def grounded(self):
        return self.support is not None


def _window(snap, wid):
    return next((w for w in snap.windows if w.id == wid), None)


def _land(body, seg, snap):
    body.y, body.vx, body.vy, body.support = seg.y, 0.0, 0.0, seg
    win = _window(snap, seg.owner) if seg.owner is not None else None
    body.owner_rect = win.rect if win else None


def _keep_support(body, snap, segs):
    owner = body.support.owner
    if owner is None:
        floor = next((s for s in segs if s.owner is None and s.spans(body.x) and abs(s.y - body.y) < 64), None)
        body.support = floor
        if floor:
            body.y = floor.y
        return
    win = _window(snap, owner)
    if win is None:
        body.support = body.owner_rect = None
        return
    if body.owner_rect is not None:
        body.x += win.rect.x - body.owner_rect.x
        body.y += win.rect.y - body.owner_rect.y
    body.owner_rect = win.rect
    body.support = support_at(segs, body.x, body.y, owner=owner)


def step(body, dt, snap, segs):
    if body.support is not None:
        _keep_support(body, snap, segs)
        if body.support is not None:
            return
    body.vy = min(body.vy + GRAVITY * dt, MAX_FALL_SPEED)
    new_x = body.x + body.vx * dt
    new_y = body.y + body.vy * dt
    seg = landing_between(segs, new_x, body.y, new_y)
    body.x = new_x
    if seg:
        _land(body, seg, snap)
        return
    body.y = new_y
    floors = [s for s in segs if s.owner is None]
    if floors and body.y > max(s.y for s in floors):  # sorti par le bas : retour au sol le plus proche
        _land(body, min(floors, key=lambda s: abs((s.x0 + s.x1) / 2 - body.x)), snap)
        body.x = min(max(body.x, body.support.x0), body.support.x1 - 1)
