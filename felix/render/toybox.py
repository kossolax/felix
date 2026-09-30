"""Boîte à jouets posée sur le bureau (planche 304, comme « SHOW TOYBOX » dans l'original).

Clic droit : jouer avec la pelote (le chat vient près de la boîte) ou ranger la boîte.
On la déplace en la faisant glisser le long du sol ; elle s'ouvre pendant la partie.
"""
import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QGuiApplication, QPainter
from PySide6.QtWidgets import QMenu, QWidget

DRAG_THRESHOLD = 4


class ToyboxWindow(QWidget):
    def __init__(self, bank, on_play, on_hide, on_moved):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Felix — boîte à jouets")
        self.on_play, self.on_hide, self.on_moved = on_play, on_hide, on_moved
        self._use_mask = sys.platform != "win32" and QGuiApplication.platformName() not in ("offscreen", "minimal")
        self.center_x = 0
        self.floor_y = 0
        self._press = None
        self._dragged = False
        self.set_bank(bank)

    def set_bank(self, bank):
        self.bank = bank
        self._frames = bank.animations["shoebox"].frames  # fermée, ouverte
        self._open = False
        self._show_frame()
        self.place(self.center_x, self.floor_y)

    def _show_frame(self):
        frame = self._frames[1 if self._open else 0]
        self.pixmap = self.bank.pixmap(frame)
        self.setFixedSize(self.pixmap.size())
        if self._use_mask:
            self.setMask(self.bank.mask(frame))
        self.update()

    def set_open(self, opened):
        if opened != self._open:
            self._open = opened
            self._show_frame()

    def place(self, center_x, floor_y):
        self.center_x, self.floor_y = round(center_x), round(floor_y)
        self.move(self.center_x - self.width() // 2, self.floor_y - self.height())

    def drag_by(self, dx):
        self.place(self.center_x + dx, self.floor_y)

    def end_drag(self):
        self.on_moved(self.center_x)

    def menu_actions(self):
        return [("Jouer avec la pelote", lambda: self.on_play(self.center_x)),
                ("Ranger la boîte à jouets", self.on_hide)]

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawPixmap(0, 0, self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._dragged = False
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu()
            for label, callback in self.menu_actions():
                action = QAction(label, menu)
                action.triggered.connect(callback)
                menu.addAction(action)
            menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        pos = event.globalPosition().toPoint()
        dx = pos.x() - self._press.x()
        if self._dragged or abs(dx) >= DRAG_THRESHOLD:
            self._dragged = True
            self.drag_by(dx)
            self._press = QPoint(pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            self._press = None
            if self._dragged:
                self.end_drag()
