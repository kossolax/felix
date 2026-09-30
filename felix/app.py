"""Application : boucle 30 Hz reliant backend de plateforme, cerveau du chat et fenêtre."""
import json
import logging
import sys
import time

from PySide6.QtCore import QElapsedTimer, QObject, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from felix import autostart
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.render.pet_window import PetWindow
from felix.render.props import PropManager

log = logging.getLogger("felix")

TICK_MS = 33
MAX_DT = 0.1
TOPMOST_MS = 2000
UPGRADE_MS = 5000
SAVE_MS = 60_000
DRAG_THRESHOLD = 6  # px : en dessous, un clic est une caresse


class FelixApp(QObject):
    def __init__(self, bank, backend, rng=None, debug=False, upgrader=None, settings=None, sound=None,
                 bank_loader=None):
        super().__init__()
        self.bank = bank
        self.bank_loader = bank_loader  # scale -> SpriteBank, pour changer de taille à chaud
        self.backend = backend
        self.settings = settings if settings is not None else QSettings("felix", "felix")
        self.sound = sound
        self.pet = Pet(bank.animations, rng, needs=self._load_needs(), scale=bank.scale)
        self.window = PetWindow(bank)
        self._last_animation = None
        self._press = None  # point d'appui tant qu'on n'a pas vraiment tiré le chat
        self.window.grabbed.connect(self._on_press)
        self.window.dragged.connect(self._on_drag)
        self.window.released.connect(self._on_release)
        if self.sound is not None:
            self.sound.enabled = self.settings.value("sound", True) not in (False, "false")
        self.window.menu_requested.connect(self.show_menu)
        self.props = PropManager(bank, on_created=self.window.raise_)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._make_tray()
        self.overlay = None
        if debug:
            self.toggle_debug(True)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self.tick)
        self.clock = QElapsedTimer()
        self.topmost_timer = None
        if sys.platform == "win32":
            from felix.platform.windows import keep_on_top
            self.topmost_timer = QTimer(self)
            self.topmost_timer.setInterval(TOPMOST_MS)
            self.topmost_timer.timeout.connect(lambda: keep_on_top(int(self.window.winId())))

        self.save_timer = QTimer(self)
        self.save_timer.setInterval(SAVE_MS)
        self.save_timer.timeout.connect(self.save)
        self.upgrade_timer = None
        if upgrader is not None:
            self.upgrade_timer = QTimer(self)
            self.upgrade_timer.setInterval(UPGRADE_MS)
            self.upgrade_timer.timeout.connect(lambda: self._try_upgrade(upgrader))

    def _try_upgrade(self, upgrader):
        new = upgrader.poll(self.backend)
        if new is not None:
            log.info("backend : passage de %s à %s", self.backend.name, new.name)
            self.backend = new
            self.upgrade_timer.stop()

    def _on_press(self, pos):
        self._press = pos

    def _on_drag(self, pos):
        if self._press is not None:
            if (pos - self._press).manhattanLength() < DRAG_THRESHOLD:
                return
            self.pet.grab(self._press.x(), self._press.y())
            self._press = None
        if self.pet.mode == "held":
            self.pet.drag(pos.x(), pos.y())

    def _on_release(self, _pos):
        if self._press is not None:
            self._press = None
            self.pet.stroke()
        elif self.pet.mode == "held":
            self.pet.release()

    def set_scale(self, big):
        scale = 2 if big else 1
        self.settings.setValue("scale", scale)
        if self.bank_loader is None or scale == self.bank.scale:
            return
        self.bank = self.bank_loader(scale)
        self.props.bank = self.bank
        self.window.set_bank(self.bank)
        self.pet.set_animations(self.bank.animations, scale)

    def set_sound(self, on):
        if self.sound is not None:
            self.sound.enabled = on
        self.settings.setValue("sound", on)

    def _load_needs(self):
        try:
            data = json.loads(self.settings.value("needs", "{}"))
        except (TypeError, ValueError):
            data = {}
        return Needs.from_dict(data, time.time()) if data else Needs()

    def save(self):
        self.settings.setValue("needs", json.dumps(self.pet.needs.to_dict(time.time())))
        self.settings.sync()

    def start(self):
        self.clock.start()
        self.timer.start()
        for extra in (self.topmost_timer, self.upgrade_timer, self.save_timer):
            if extra is not None:
                extra.start()

    def tick(self, dt=None):
        if dt is None:
            dt = min(self.clock.restart() / 1000.0, MAX_DT)
        snap = self.backend.snapshot()
        view = self.pet.update(dt, snap)
        if view.animation != self._last_animation:
            self._last_animation = view.animation
            log.debug("animation %s", view.animation)
        self.window.show_view(view)
        for event in view.events:
            self.dispatch(event)
        if self.overlay is not None:
            self.overlay.set_state(snap, self.pet)
        return view

    def dispatch(self, event):
        """Événement du chat : un son (str) ou un accessoire à afficher (tuple)."""
        if isinstance(event, tuple):
            self.props.handle(event)
        elif self.sound is not None:
            self.sound.play(event)

    def toggle_debug(self, on):
        from felix.render.debug_overlay import DebugOverlay
        if on and self.overlay is None:
            self.overlay = DebugOverlay()
            self.overlay.show()
        elif not on and self.overlay is not None:
            self.overlay.close()
            self.overlay = None

    def menu_actions(self):
        """(libellé, rappel, coché ou None) — partagé par le menu clic droit et le tray."""
        needs = self.pet.needs
        status = f"Faim {round(needs.hunger * 100)} % · Soif {round(needs.thirst * 100)} %"
        return [
            ("Nourrir", lambda _=False: self.pet.request("feed"), None),
            ("Donner du lait", lambda _=False: self.pet.request("drink"), None),
            ("Jouer avec la pelote", lambda _=False: self.pet.request("yarn"), None),
            ("Regarder la télé", lambda _=False: self.pet.request("tv"), None),
            (status, None, None),
            None,
            ("Rester immobile", lambda on: setattr(self.pet, "still", on), self.pet.still),
            ("Sons", self.set_sound, self.sound.enabled if self.sound is not None else False),
            ("Grande taille (×2)", self.set_scale, self.bank.scale == 2),
            ("Lancer au démarrage", autostart.set_enabled, autostart.is_enabled()),
            None,
            ("Débogage", self.toggle_debug, self.overlay is not None),
            ("À propos…", lambda _=False: self.show_about(), None),
            None,
            ("Quitter", lambda _=False: self.quit(), None),
        ]

    def _make_tray(self):
        walk = self.bank.animations["sit_front"].frames[0]
        icon = QIcon(QPixmap(self.bank.pixmap(walk)))
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Virtual Felix")
        self._tray_menu = QMenu()
        self._tray_menu.aboutToShow.connect(lambda: self.fill_menu(self._tray_menu))
        self.tray.setContextMenu(self._tray_menu)
        self.tray.show()

    def about_text(self):
        return ("<b>Virtual Felix</b> — le chat de bureau, de retour sur Linux et Windows.<br><br>"
                "Graphismes : <i>Felix II / Virtual Felix</i> (ScreenMates, AdTools et Ogilvy pour Purina "
                "Felix, 1999-2000), extraits de l'exécutable d'origine conservé sur archive.org, pour un "
                "usage personnel.<br>"
                "Sons : enregistrements CC0 et du domaine public de Wikimedia Commons (voir "
                "assets/sounds/CREDITS.md).<br><br>"
                "Clic gauche : caresser — glisser : attraper — clic droit : ce menu.")

    def show_about(self):
        QMessageBox.about(None, "À propos de Virtual Felix", self.about_text())

    def fill_menu(self, menu):
        menu.clear()
        for item in self.menu_actions():
            if item is None:
                menu.addSeparator()
                continue
            label, callback, checked = item
            action = QAction(label, menu)
            if callback is None:
                action.setEnabled(False)
            else:
                action.triggered.connect(callback)
            if checked is not None:
                action.setCheckable(True)
                action.setChecked(checked)
            menu.addAction(action)

    def show_menu(self, pos):
        menu = QMenu()
        self.fill_menu(menu)
        menu.exec(pos)

    def quit(self):
        self.save()
        self.timer.stop()
        if self.tray is not None:
            self.tray.hide()
        self.backend.stop()
        QApplication.quit()
