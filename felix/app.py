"""Application : boucle 30 Hz reliant backend de plateforme, cerveau du chat et fenêtre."""
from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu

from felix.core.pet import Pet
from felix.render.pet_window import PetWindow

TICK_MS = 33
MAX_DT = 0.1


class FelixApp(QObject):
    def __init__(self, bank, backend, rng=None, debug=False):
        super().__init__()
        self.bank = bank
        self.backend = backend
        self.pet = Pet(bank.animations, rng)
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

    def start(self):
        self.clock.start()
        self.timer.start()

    def tick(self, dt=None):
        if dt is None:
            dt = min(self.clock.restart() / 1000.0, MAX_DT)
        snap = self.backend.snapshot()
        view = self.pet.update(dt, snap)
        self.window.show_view(view)
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
        return [
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
            if checked is not None:
                action.setCheckable(True)
                action.setChecked(checked)
            action.triggered.connect(callback)
            menu.addAction(action)
        menu.exec(pos)

    def quit(self):
        self.timer.stop()
        self.backend.stop()
        QApplication.quit()
