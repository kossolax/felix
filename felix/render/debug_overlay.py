"""Superposition de débogage : fenêtres détectées, surfaces marchables, curseur, état du chat.

Entièrement traversée par les clics (WindowTransparentForInput), un pixel en
retrait des bords de l'écran pour ne pas être pris pour une fenêtre plein écran.
"""
import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class DebugOverlay(QWidget):
    def __init__(self):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        area = QRect()
        for screen in QGuiApplication.screens():
            area = area.united(screen.geometry())
        self.setGeometry(area.adjusted(1, 1, -1, -1))
        self.snap = None
        self.pet = None

    def set_state(self, snap, pet):
        self.snap, self.pet = snap, pet
        self.update()

    def paintEvent(self, _event):
        if self.snap is None:
            return
        p = QPainter(self)
        p.translate(-self.x(), -self.y())
        p.setPen(QPen(QColor(0, 160, 255, 200), 1, Qt.PenStyle.DashLine))
        for m in self.snap.monitors:
            w = m.workarea
            p.drawRect(w.x, w.y, w.w - 1, w.h - 1)
        for i, win in enumerate(self.snap.windows):
            r = win.rect
            p.setPen(QPen(QColor(255, 200, 0, 220), 1))
            p.drawRect(r.x, r.y, r.w - 1, r.h - 1)
            p.drawText(r.x + 4, r.y + 14, f"#{i} id={win.id}{' FS' if win.fullscreen else ''}")
        p.setPen(QPen(QColor(0, 255, 90, 230), 3))
        for s in self.pet.segments:
            p.drawLine(s.x0, s.y, s.x1 - 1, s.y)
        if self.snap.cursor:
            cx, cy = self.snap.cursor
            p.setPen(QPen(QColor(255, 60, 60), 2))
            p.drawEllipse(cx - 8, cy - 8, 16, 16)
        body = self.pet.body
        if body is not None:
            p.setPen(QPen(QColor(255, 0, 255), 2))
            p.drawLine(int(body.x) - 6, int(body.y), int(body.x) + 6, int(body.y))
            action = type(self.pet.action).__name__ if self.pet.action else "-"
            anim = self.pet.player.animation.name if self.pet.player else "-"
            p.drawText(int(body.x) + 10, int(body.y) - 10, f"{self.pet.mode} {action} {anim}")
