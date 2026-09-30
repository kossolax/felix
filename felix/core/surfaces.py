"""Surfaces sur lesquelles le chat peut marcher : bas des zones utiles et haut des fenêtres."""
from dataclasses import dataclass

CEILING_TOLERANCE = 2  # une fenêtre collée en haut de la zone utile (maximisée) est un plafond
MIN_LENGTH = 24  # trop court pour y poser le chat
SUPPORT_TOLERANCE = 0.5


@dataclass(frozen=True)
class Segment:
    y: int
    x0: int
    x1: int
    owner: int = None  # id de la fenêtre, None pour le sol d'un écran

    def spans(self, x):
        return self.x0 <= x < self.x1


def _monitor_for(monitors, x, y):
    for m in monitors:
        if m.geometry.contains(x, y):
            return m
    return min(monitors, key=lambda m: m.geometry.distance2(x, y)) if monitors else None


def _subtract(intervals, a, b):
    out = []
    for x0, x1 in intervals:
        if b <= x0 or a >= x1:
            out.append((x0, x1))
            continue
        if x0 < a:
            out.append((x0, a))
        if b < x1:
            out.append((b, x1))
    return out


def _floors(monitors):
    """Bas des zones utiles ; ceux d'écrans voisins à la même hauteur ne forment qu'un sol."""
    floors = []
    for m in sorted(monitors, key=lambda m: (m.workarea.bottom, m.workarea.x)):
        wa = m.workarea
        last = floors[-1] if floors else None
        if last and last.y == wa.bottom and last.x1 >= wa.x:
            floors[-1] = Segment(last.y, last.x0, max(last.x1, wa.right), None)
        else:
            floors.append(Segment(wa.bottom, wa.x, wa.right, None))
    return floors


def compute_surfaces(snap):
    segs = _floors(snap.monitors)
    windows = snap.windows
    for i, win in enumerate(windows):
        r = win.rect
        if win.fullscreen:
            continue
        mon = _monitor_for(snap.monitors, r.x + r.w // 2, r.y)
        if mon is None or r.y <= mon.workarea.y + CEILING_TOLERANCE or r.y >= mon.workarea.bottom:
            continue
        intervals = [(max(r.x, mon.geometry.x), min(r.right, mon.geometry.right))]
        for above in windows[:i]:
            if not above.fullscreen and above.rect.y <= r.y < above.rect.bottom:
                intervals = _subtract(intervals, above.rect.x, above.rect.right)
        segs.extend(Segment(r.y, x0, x1, win.id) for x0, x1 in intervals if x1 - x0 >= MIN_LENGTH)
    return segs


def support_at(segs, x, y, owner=...):
    for s in segs:
        if s.spans(x) and abs(s.y - y) <= SUPPORT_TOLERANCE and (owner is ... or s.owner == owner):
            return s
    return None


def landing_between(segs, x, y0, y1):
    """Segment le plus haut sous x avec y0 <= y <= y1."""
    hits = [s for s in segs if s.spans(x) and y0 <= s.y <= y1]
    return min(hits, key=lambda s: s.y) if hits else None
