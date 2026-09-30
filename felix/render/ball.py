"""Balle libre (pelote, ballon…) : suit la physique du cœur ; on peut l'attraper et la lancer."""
import sys
import time
from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

THROW_WINDOW = 0.1  # s : la vitesse du lancer est celle du geste sur ses dernières 100 ms


class BallWindow(QWidget):
    def __init__(self, bank, on_grab, on_drag, on_throw):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Felix — pelote")
        self.on_grab, self.on_drag, self.on_throw = on_grab, on_drag, on_throw
        self._use_mask = sys.platform != "win32" and QGuiApplication.platformName() not in ("offscreen", "minimal")
        self._pos = (0.0, 0.0)  # point de contact affiché
        self._grab = None  # décalage point de contact − pointeur pendant qu'on la tient
        self._samples = deque(maxlen=16)
        self._frame_index = None
        self.pixmap = None
        self.set_bank(bank)

    def set_bank(self, bank):
        self.bank = bank
        self._use("yarn_ball")

    def _use(self, anim):
        self._anim = anim
        self._frames = self.bank.animations[anim].frames
        self._frame_index = None
        self._show_frame(0)

    @property
    def dragging(self):
        return self._grab is not None

    def _show_frame(self, index):
        if index == self._frame_index:
            return
        self._frame_index = index
        frame = self._frames[index]
        self.pixmap = self.bank.pixmap(frame)
        self.setFixedSize(self.pixmap.size())
        if self._use_mask:
            self.setMask(self.bank.mask(frame))
        self.update()

    def _place(self, x, y):
        self._pos = (x, y)
        ax, ay = self._frames[self._frame_index].anchor
        self.move(round(x) - ax, round(y) - ay)

    def show_view(self, view):
        """Affiche la pelote du cœur (BallView), ou la cache (None, ou dessinée par le chat)."""
        if view is None or not view.visible:
            self.hide()
            return
        if view.anim != self._anim:
            self._use(view.anim)
        self._show_frame(view.frame)
        self._place(view.x, view.y)
        if not self.isVisible():
            self.show()

    def grab_at(self, px, py, t):
        self._grab = (self._pos[0] - px, self._pos[1] - py)
        self._samples.clear()
        self._samples.append((t, px, py))
        self.on_grab()

    def drag_to(self, px, py, t):
        self._samples.append((t, px, py))
        x, y = px + self._grab[0], py + self._grab[1]
        self._place(x, y)
        self.on_drag(x, y)

    def release(self, t):
        recent = [s for s in self._samples if s[0] >= t - THROW_WINDOW]
        vx = vy = 0.0
        if len(recent) >= 2 and recent[-1][0] > recent[0][0]:
            (t0, x0, y0), (t1, x1, y1) = recent[0], recent[-1]
            vx, vy = (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
        self._grab = None
        self.on_throw(vx, vy)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawPixmap(0, 0, self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition()
            self.grab_at(pos.x(), pos.y(), time.monotonic())

    def mouseMoveEvent(self, event):
        if self.dragging:
            pos = event.globalPosition()
            self.drag_to(pos.x(), pos.y(), time.monotonic())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.release(time.monotonic())
