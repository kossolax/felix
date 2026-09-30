"""Interprétation des propriétés EWMH/GTK (sans connexion X, testable)."""
from felix.core.world import Rect

ALL_DESKTOPS = 0xFFFFFFFF
KEPT_TYPES = {"_NET_WM_WINDOW_TYPE_NORMAL", "_NET_WM_WINDOW_TYPE_DIALOG"}


def frame_rect(x, y, w, h, net_extents, gtk_extents):
    """Rectangle visible : client + décorations serveur (_NET_FRAME_EXTENTS) − ombres CSD (_GTK_FRAME_EXTENTS).

    Les extents sont (gauche, droite, haut, bas).
    """
    if net_extents:
        left, right, top, bottom = net_extents
        x, y, w, h = x - left, y - top, w + left + right, h + top + bottom
    if gtk_extents:
        left, right, top, bottom = gtk_extents
        x, y, w, h = x + left, y + top, w - left - right, h - top - bottom
    return Rect(x, y, w, h)


def is_candidate(types, states, desktop, current_desktop):
    if types and not KEPT_TYPES.intersection(types):
        return False
    if "_NET_WM_STATE_HIDDEN" in states:
        return False
    return desktop is None or desktop in (ALL_DESKTOPS, current_desktop)


def _intersect(a, b):
    x0, y0 = max(a.x, b.x), max(a.y, b.y)
    x1, y1 = min(a.right, b.right), min(a.bottom, b.bottom)
    return Rect(x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None


def workareas_for(values, monitors):
    """values : suite de (x, y, w, h). Associe à chaque moniteur la zone qui le recouvre le plus."""
    rects = [Rect(*values[i:i + 4]) for i in range(0, len(values) - len(values) % 4, 4)]
    out = []
    for mon in monitors:
        best = None
        for r in rects:
            inter = _intersect(r, mon)
            if inter and (best is None or inter.w * inter.h > best.w * best.h):
                best = inter
        out.append(best or mon)
    return out
