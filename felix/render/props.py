"""Accessoires laissés à l'écran par le chat (traces de pattes, griffures, placard qui s'efface) : petites fenêtres
transparentes, traversées par les clics, qui s'effacent en fondu."""
import random
import sys

from PySide6.QtCore import QPropertyAnimation, QRect, QTimer, Qt
from PySide6.QtGui import QBitmap, QColor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

FADE_MS = 3000
CLAW_WIDTH = 28
GHOST_HOLD = 0.15  # s : fantôme tramé d'un accessoire qui disparaît (le placard)…
GHOST_FADE_MS = 350  # … puis fondu


_MASKS = {}


def shape_masks():
    """Découper les fenêtres à la forme de l'accessoire : sous X11 sans compositeur, sinon il s'affiche
    dans un rectangle noir ; Windows gère la transparence au pixel."""
    return sys.platform != "win32" and QGuiApplication.platformName() not in ("offscreen", "minimal")


class PropWindow(QWidget):
    def __init__(self, pixmap, x, y, lifetime, fade_ms=FADE_MS, masked=False):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform.startswith("linux"):
            flags |= Qt.WindowType.X11BypassWindowManagerHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.masked = masked
        self.closed = False
        self.lifetime, self.fade_ms = lifetime, fade_ms
        self.setGeometry(QRect(round(x), round(y), pixmap.width(), pixmap.height()))
        self._set_pixmap(pixmap)
        self._fade = None
        self._life = QTimer(self)
        self._life.setSingleShot(True)
        self._life.timeout.connect(self.fade_out)
        self._life.start(int(lifetime * 1000))

    def _set_pixmap(self, pixmap):
        self.pixmap = pixmap
        if self.masked:
            key = pixmap.cacheKey()
            if key not in _MASKS:  # une même image répétée (les rayures, 100 fois) : un seul calcul
                if len(_MASKS) > 256:
                    _MASKS.clear()
                _MASKS[key] = QRegion(QBitmap.fromImage(pixmap.toImage().createAlphaMask()))
            self.setMask(_MASKS[key])

    def closeEvent(self, event):
        self.closed = True
        super().closeEvent(event)

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
        self._fade.setDuration(self.fade_ms)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.close)
        self._fade.start()


class AnimPropWindow(PropWindow):
    """Accessoire animé qui se joue une fois puis disparaît (ex. la déchirure qui se referme)."""

    def __init__(self, pixmaps, x, y, fps, masked=False):
        super().__init__(pixmaps[0], x, y, lifetime=3600, masked=masked)
        self.frames = list(pixmaps)
        self.index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.advance)
        self._timer.start(int(1000 / fps))

    def advance(self):
        self.index += 1
        if self.index >= len(self.frames):
            self._timer.stop()
            self.close()
            return
        self._set_pixmap(self.frames[self.index])
        self.update()


CLAW_STEP = 8  # px entre deux ondulations d'une griffure


def claw_pixmap(height, wiggle):
    """Quatre griffures légèrement ondulées, blanches cernées de gris, sur `height` pixels. Tracées
    depuis le bas : `wiggle[i][k]`, écart du trait k au i-ième pas de CLAW_STEP px au-dessus du bas
    (une griffure qui s'allonge vers le haut garde ainsi le même bas)."""
    pix = QPixmap(CLAW_WIDTH, max(height, 1))
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    steps = -(-height // CLAW_STEP)
    for k in range(4):
        x = 4 + k * 6.5
        path = QPainterPath()
        path.moveTo(x, height)
        for i in range(steps):
            path.lineTo(x + wiggle[i][k], max(height - (i + 1) * CLAW_STEP, 0))
        p.setPen(QPen(QColor(60, 60, 60, 150), 3.2))
        p.drawPath(path)
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.4))
        p.drawPath(path)
    p.end()
    return pix


class ClawWindow(PropWindow):
    """Griffures d'une escalade : elles s'allongent vers le haut à mesure que le chat grimpe, et
    ne commencent à s'effacer qu'une fois la montée finie."""

    def __init__(self, x, top, bottom, lifetime, rng, masked=False):
        self.bottom, self.rng, self.wiggle = round(bottom), rng, []
        super().__init__(self._draw(round(top)), x, top, lifetime, masked=masked)

    def _draw(self, top):
        height = max(self.bottom - top, 1)
        while len(self.wiggle) * CLAW_STEP < height:
            self.wiggle.append([self.rng.uniform(-1.2, 1.2) for _ in range(4)])
        return claw_pixmap(height, self.wiggle)

    def grow(self, top):
        top = round(top)
        if top >= self.y():
            return
        pixmap = self._draw(top)
        self.setGeometry(QRect(self.x(), top, pixmap.width(), pixmap.height()))
        self._set_pixmap(pixmap)
        self.update()
        self._life.start(int(self.lifetime * 1000))  # le temps d'affichage court depuis le dernier coup de griffe


class PropManager:
    def __init__(self, bank, lifetime=40.0, limit=16, on_created=None, masked=None):
        self.bank = bank
        self.lifetime = lifetime
        self.limit = limit
        self.on_created = on_created  # ex. remettre le chat au-dessus des accessoires
        self.masked = shape_masks() if masked is None else masked
        self.hidden = False  # derrière une appli en plein écran, comme le chat
        self.windows = []
        self._climbs = {}  # griffures d'une escalade en cours, par montée
        self.rng = random.Random()

    def set_hidden(self, hidden):
        if hidden == self.hidden:
            return
        self.hidden = hidden
        for w in self.windows:
            if not w.closed:
                w.setVisible(not hidden)
        if not hidden and self.on_created is not None:
            self.on_created()  # le chat repasse devant ses accessoires

    def handle(self, event):
        if not isinstance(event, tuple):
            return
        kind = event[0]
        if kind == "marks":
            for (sheet, sx, sy, w, h), (x, y) in event[1]:
                pix = QPixmap.fromImage(self.bank.sheets[sheet].copy(QRect(sx, sy, w, h)))
                self._add(PropWindow(pix, x, y, self.lifetime, masked=self.masked))
        elif kind == "ghost":
            _, (sheet, sx, sy, w, h), (x, y) = event
            pix = QPixmap.fromImage(self.bank.sheets[sheet].copy(QRect(sx, sy, w, h)))
            self._add(PropWindow(pix, x, y, GHOST_HOLD, GHOST_FADE_MS, masked=self.masked))
        elif kind == "prop_anim":
            _, name, (x, y), mirrored = event
            anim = self.bank.animations[name]
            self._add(AnimPropWindow([self.bank.pixmap(f, mirrored) for f in anim.frames], x, y, anim.fps,
                                     masked=self.masked))
        elif kind == "claws":
            _, x, top, bottom, *climb = event  # climb : la montée dont elles font partie, qui les allonge
            window = self._climbs.get(climb[0]) if climb else None
            if window is not None and not window.closed:
                window.grow(top)
                return
            window = ClawWindow(x - CLAW_WIDTH / 2, top, bottom, self.lifetime, self.rng, masked=self.masked)
            if climb:
                self._climbs = {k: w for k, w in self._climbs.items() if not w.closed}
                self._climbs[climb[0]] = window
            self._add(window)

    def _add(self, window):
        self.windows = [w for w in self.windows if not w.closed]
        self.windows.append(window)
        if not self.hidden:
            window.show()
        while len(self.windows) > self.limit:
            self.windows.pop(0).close()
        if self.on_created is not None:
            self.on_created()
