"""Application : boucle 30 Hz reliant backend de plateforme, cerveau du chat et fenêtre."""
import json
import logging
import sys
import time

from PySide6.QtCore import QElapsedTimer, QObject, QSettings, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu

from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.render.pet_window import PetWindow

TICK_MS = 33
MAX_DT = 0.1
TOPMOST_MS = 2000
UPGRADE_MS = 5000
SAVE_MS = 60_000


class FelixApp(QObject):
    def __init__(self, bank, backend, rng=None, debug=False, upgrader=None, settings=None, sound=None):
        super().__init__()
        self.bank = bank
        self.backend = backend
        self.settings = settings if settings is not None else QSettings("felix", "felix")
        self.sound = sound
        self.pet = Pet(bank.animations, rng, needs=self._load_needs())
        self.window = PetWindow(bank)
        self.window.grabbed.connect(lambda p: self.pet.grab(p.x(), p.y()))
        self.window.dragged.connect(lambda p: self.pet.drag(p.x(), p.y()))
        self.window.released.connect(lambda p: self.pet.release())
        self.window.menu_requested.connect(self.show_menu)
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
            logging.getLogger("felix").info("backend : passage de %s à %s", self.backend.name, new.name)
            self.backend = new
            self.upgrade_timer.stop()

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
        self.window.show_view(view)
        if self.sound is not None:
            for event in view.events:
                self.sound.play(event)
        if self.overlay is not None:
            self.overlay.set_state(snap, self.pet)
        return view

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
            (status, None, None),
            None,
            ("Rester immobile", lambda on: setattr(self.pet, "still", on), self.pet.still),
            None,
            ("Débogage", self.toggle_debug, self.overlay is not None),
            None,
            ("Quitter", lambda _=False: self.quit(), None),
        ]

    def show_menu(self, pos):
        menu = QMenu()
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
        menu.exec(pos)

    def quit(self):
        self.save()
        self.timer.stop()
        self.backend.stop()
        QApplication.quit()
