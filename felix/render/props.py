"""Accessoires laissés à l'écran par le chat (traces de pattes, griffures) : petites fenêtres
transparentes, traversées par les clics, qui s'effacent en fondu."""
import random
import sys

from PySide6.QtCore import QPropertyAnimation, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

FADE_MS = 3000
CLAW_WIDTH = 28


class PropWindow(QWidget):
    def __init__(self, pixmap, x, y, lifetime):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.pixmap = pixmap
        self.setGeometry(QRect(round(x), round(y), pixmap.width(), pixmap.height()))
        self._fade = None
        QTimer.singleShot(int(lifetime * 1000), self.fade_out)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawPixmap(0, 0, self.pixmap)

    def fade_out(self):
        if self._fade is not None:
            return
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(FADE_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.close)
        self._fade.start()


def claw_pixmap(height, rng):
    """Quatre griffures légèrement ondulées, blanches cernées de gris, sur `height` pixels."""
    pix = QPixmap(CLAW_WIDTH, max(height, 1))
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for k in range(4):
        x = 4 + k * 6.5
        path = QPainterPath()
        path.moveTo(x, 0)
        for y in range(8, height + 8, 8):
            path.lineTo(x + rng.uniform(-1.2, 1.2), min(y, height))
        p.setPen(QPen(QColor(60, 60, 60, 150), 3.2))
        p.drawPath(path)
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.4))
        p.drawPath(path)
    p.end()
    return pix


class PropManager:
    def __init__(self, bank, lifetime=40.0, limit=16, on_created=None):
        self.bank = bank
        self.lifetime = lifetime
        self.limit = limit
        self.on_created = on_created  # ex. remettre le chat au-dessus des accessoires
        self.windows = []
        self.rng = random.Random()

    def handle(self, event):
        if not isinstance(event, tuple):
            return
        kind = event[0]
        if kind == "marks":
            for (sheet, sx, sy, w, h), (x, y) in event[1]:
                pix = QPixmap.fromImage(self.bank.sheets[sheet].copy(QRect(sx, sy, w, h)))
                self._add(PropWindow(pix, x, y, self.lifetime))
        elif kind == "claws":
            _, x, top, bottom = event
            self._add(PropWindow(claw_pixmap(round(bottom - top), self.rng), x - CLAW_WIDTH / 2, top, self.lifetime))

    def _add(self, window):
        self.windows = [w for w in self.windows if w.isVisible() or w is window]
        self.windows.append(window)
        window.show()
        while len(self.windows) > self.limit:
            self.windows.pop(0).close()
        if self.on_created is not None:
            self.on_created()
