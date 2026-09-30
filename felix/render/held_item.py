"""Objet tenu au bout du curseur pour le chat (extension Feeding) : boîte de pâtée, brique de lait
ou sachet de friandises. Il suit le curseur ; clic gauche : servir (ou verser une friandise),
clic droit : le reprendre."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

# objet : (apparition, tenu, clic, disparition) — animations du manifeste (None : aucune)
ITEMS = {
    "can": ("can_show", "can_held", None, "can_hide"),
    "carton": ("carton_carry", "carton_carry", None, None),
    "treats": ("treats_bag_in", "treats_bag_hold", "treats_bag_pour", "treats_bag_out"),
}
POUR_DROP = 4  # la friandise sort à la 5e image du sachet qui verse


class HeldItemWindow(QWidget):
    def __init__(self, bank, on_click, on_cancel):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Felix — pour le chat")
        self.on_click, self.on_cancel = on_click, on_cancel
        self.bank = bank
        self.kind = None
        self.pixmap = None
        self.anchor = (0, 0)
        self._queue = []  # animations à jouer, puis la dernière en boucle (None : disparaître)
        self._anim = None
        self._t = 0.0
        self._on_frame = None  # (image, rappel) pendant l'animation en cours
        self._pos = (0, 0)

    @property
    def active(self):
        return self.kind is not None

    def hold(self, kind):
        self.kind = kind
        show, held, _pour, _out = ITEMS[kind]
        self._play([show, held])
        self.show()

    def pour(self, on_drop):
        """Le sachet verse : `on_drop()` à l'image où la friandise sort, puis il se redresse."""
        _show, held, pour, _out = ITEMS[self.kind]
        self._play([pour, "treats_bag_up", held], on_frame=(POUR_DROP, on_drop))

    @property
    def pouring(self):
        return self._anim is not None and self._anim.name in ("treats_bag_pour", "treats_bag_up")

    def release(self):
        """L'objet disparaît (sur place, à sa façon)."""
        if self.kind is None:
            return
        out = ITEMS[self.kind][3]
        self.kind = None
        if out is None:
            self._stop()
        else:
            self._play([out, None])

    def _play(self, names, on_frame=None):
        self._queue = list(names)
        self._on_frame = on_frame
        self._next()

    def _next(self):
        name = self._queue.pop(0)
        if name is None:
            self._stop()
            return
        self._anim = self.bank.animations[name]
        self._t = 0.0
        self._show_frame(0)

    def _stop(self):
        self._anim = None
        self._queue = []
        self.hide()

    def _show_frame(self, index):
        frame = self._anim.frames[index]
        self.pixmap = self.bank.pixmap(frame)
        self.anchor = frame.anchor
        self.setFixedSize(self.pixmap.size())
        self._place()
        self.update()

    def follow(self, x, y):
        self._pos = (round(x), round(y))
        self._place()

    def _place(self):
        self.move(self._pos[0] - self.anchor[0], self._pos[1] - self.anchor[1])

    def tick(self, dt):
        if self._anim is None:
            return
        before = int(self._t * self._anim.fps)
        self._t += dt
        index = int(self._t * self._anim.fps)
        count = len(self._anim.frames)
        if self._on_frame and before < self._on_frame[0] <= index and self._anim.name.endswith("_pour"):
            self._on_frame[1]()
        if index >= count:
            if self._queue:
                if self._anim.name.endswith("_pour"):
                    self._on_frame = None
                self._next()
                return
            index %= count  # tenu : en boucle
            self._t %= count / self._anim.fps
        self._show_frame(index)

    def click_left(self, x, y):
        if self.kind is not None:
            self.on_click(x, y)

    def click_right(self):
        if self.kind is not None:
            self.on_cancel()

    def paintEvent(self, _event):
        if self.pixmap is None:
            return
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawPixmap(0, 0, self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition()
            self.click_left(pos.x(), pos.y())
        elif event.button() == Qt.MouseButton.RightButton:
            self.click_right()
