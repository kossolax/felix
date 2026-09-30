"""Backend minimal : écrans et zones utiles vus par Qt, sans fenêtres.

Utilisé sous Wayland sans l'extension GNOME (le curseur y est inconnu), et en
secours partout ailleurs.
"""
from PySide6.QtGui import QCursor, QGuiApplication

from felix.core.world import Monitor, Rect, WorldSnapshot


def _rect(q):
    return Rect(q.x(), q.y(), q.width(), q.height())


def qt_monitors():
    return tuple(Monitor(_rect(s.geometry()), _rect(s.availableGeometry())) for s in QGuiApplication.screens())


class QtScreensBackend:
    name = "degraded"

    def __init__(self, cursor=False):
        self.cursor = cursor

    def snapshot(self):
        pos = QCursor.pos() if self.cursor else None
        return WorldSnapshot(monitors=qt_monitors(), windows=(),
                             cursor=(pos.x(), pos.y()) if pos is not None else None)

    def stop(self):
        pass
