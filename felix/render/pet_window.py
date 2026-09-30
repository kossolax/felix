"""Fenêtre du chat : sans cadre, transparente, au premier plan, traversée par les clics hors du chat.

La fenêtre a une taille fixe qui englobe toutes les images autour du point des
pieds ; seul move() est appelé à chaque tick, jamais resize().
"""
import sys
from dataclasses import dataclass

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class Extents:
    left: int
    right: int
    up: int
    down: int

    @property
    def width(self):
        return self.left + self.right

    @property
    def height(self):
        return self.up + self.down

    def window_origin(self, view):
        return round(view.x) - self.left, round(view.y) - self.up

    def frame_offset(self, frame, mirrored):
        ax = frame.rect[2] - frame.anchor[0] if mirrored else frame.anchor[0]
        return self.left - ax, self.up - frame.anchor[1]


def compute_extents(animations):
    side = up = down = 0
    for anim in animations.values():
        for f in anim.frames:
            w, h = f.rect[2], f.rect[3]
            ax, ay = f.anchor
            side = max(side, ax, w - ax)
            up = max(up, ay)
            down = max(down, h - ay)
    return Extents(side, side, up, down)


class PetWindow(QWidget):
    grabbed = Signal(QPoint)
    dragged = Signal(QPoint)
    released = Signal(QPoint)
    menu_requested = Signal(QPoint)

    def __init__(self, bank):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform.startswith("linux"):
            # override-redirect : ni barre des tâches ni alt-tab, sur tous les bureaux
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setWindowTitle("Felix")
        self.bank = bank
        self.extents = compute_extents(bank.animations)
        self.setFixedSize(self.extents.width, self.extents.height)
        self._use_mask = sys.platform != "win32"  # Windows : test de clic par pixel des fenêtres layered
        self._key = None
        self._pixmap = None
        self._offset = (0, 0)
        self._dragging = False

    def show_view(self, view):
        if view.hidden:
            if self.isVisible():
                self.hide()
            return
        key = (view.frame, view.mirrored)
        if key != self._key:
            self._key = key
            self._pixmap = self.bank.pixmap(view.frame, view.mirrored)
            self._offset = self.extents.frame_offset(view.frame, view.mirrored)
            if self._use_mask:
                self.setMask(self.bank.mask(view.frame, view.mirrored).translated(*self._offset))
            self.update()
        x, y = self.extents.window_origin(view)
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)
        if not self.isVisible():
            self.show()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        if self._pixmap is not None:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.drawPixmap(*self._offset, self._pixmap)

    def mousePressEvent(self, event):
        pos = event.globalPosition().toPoint()
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.grabbed.emit(pos)
        elif event.button() == Qt.MouseButton.RightButton:
            self.menu_requested.emit(pos)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.dragged.emit(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.released.emit(event.globalPosition().toPoint())
