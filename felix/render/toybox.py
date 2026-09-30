"""Boîte à jouets posée sur le bureau (planche 304, comme « SHOW TOYBOX » dans l'original).

Clic droit : jouer avec la pelote (le chat vient près de la boîte) ou ranger la boîte.
On la déplace en la faisant glisser le long du sol ; elle s'ouvre pendant la partie.
"""
import sys

from PySide6.QtCore import Qt
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
        self._press_x = None  # abscisse du pointeur à l'appui, tant qu'on n'a pas bougé
        self._grab = None  # décalage pointeur − centre pendant un glisser
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

    @property
    def dragging(self):
        return self._grab is not None

    def begin_drag(self, pointer_x):
        self._grab = pointer_x - self.center_x

    def drag_to(self, pointer_x):
        """Le point attrapé reste sous le pointeur ; l'appli recale la boîte au relâchement."""
        self.place(pointer_x - self._grab, self.floor_y)

    def end_drag(self):
        self._grab = None
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
            self._press_x = event.globalPosition().x()
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu()
            for label, callback in self.menu_actions():
                action = QAction(label, menu)
                action.triggered.connect(callback)
                menu.addAction(action)
            menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        x = round(event.globalPosition().x())
        if self._press_x is not None and not self.dragging and abs(x - self._press_x) >= DRAG_THRESHOLD:
            self.begin_drag(round(self._press_x))
        if self.dragging:
            self.drag_to(x)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_x = None
            if self.dragging:
                self.end_drag()
