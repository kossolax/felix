"""Application : boucle 30 Hz reliant backend de plateforme, cerveau du chat et fenêtre."""
import json
import logging
import sys
import time

from PySide6.QtCore import QElapsedTimer, QObject, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from felix import __version__, autostart
from felix.core.needs import Needs
from felix.core.pet import Pet
from felix.core.surfaces import monitor_for
from felix.render.ball import BallWindow
from felix.render.pet_window import PetWindow
from felix.render.props import PropManager
from felix.render.toybox import ToyboxWindow

log = logging.getLogger("felix")

TICK_MS = 33
MAX_DT = 0.1
TOPMOST_MS = 2000
UPGRADE_MS = 5000
SAVE_MS = 60_000
LEAVE_TIMEOUT = 8.0  # s : on ferme même si le chat n'a pas pu passer sa chatière
DRAG_THRESHOLD = 6  # px : en dessous, un clic est une caresse


class FelixApp(QObject):
    def __init__(self, bank, backend, rng=None, debug=False, upgrader=None, settings=None, sound=None,
                 bank_loader=None, speed=1.0):
        super().__init__()
        self.bank = bank
        self.bank_loader = bank_loader  # scale -> SpriteBank, pour changer de taille à chaud
        self.backend = backend
        self.settings = settings if settings is not None else QSettings("felix", "felix")
        self.sound = sound
        self.pet = Pet(bank.animations, rng, needs=self._load_needs(), scale=bank.scale)
        self.window = PetWindow(bank)
        self._last_animation = None
        self._quitting = False
        self._quit_elapsed = 0.0
        self.quitting_done = False
        self.speed = speed  # accéléré ou ralenti pour les tests (--speed), pas dans le menu
        self._press = None  # point d'appui tant qu'on n'a pas vraiment tiré le chat
        self.window.grabbed.connect(self._on_press)
        self.window.dragged.connect(self._on_drag)
        self.window.released.connect(self._on_release)
        if self.sound is not None:
            self.sound.enabled = self.settings.value("sound", True) not in (False, "false")
        self.window.menu_requested.connect(self.show_menu)
        self.props = PropManager(bank, on_created=self.window.raise_)
        self.toybox = ToyboxWindow(bank, on_play=self._play_from_toybox, on_hide=lambda: self.set_toybox(False),
                                   on_moved=self._toybox_dropped)
        self._toybox_on = False  # rangée à chaque démarrage ; seule sa place est retenue
        self._snap = None
        self.ball_window = BallWindow(bank, on_grab=self.pet.grab_ball, on_drag=self.pet.drag_ball,
                                      on_throw=self._ball_thrown)
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
        """Taille ×2 à chaud (tests ; au démarrage : --scale 2)."""
        scale = 2 if big else 1
        if self.bank_loader is None or scale == self.bank.scale:
            return
        self.bank = self.bank_loader(scale)
        self.props.bank = self.bank
        self.window.set_bank(self.bank)
        self.toybox.set_bank(self.bank)
        self.ball_window.set_bank(self.bank)
        self.pet.set_animations(self.bank.animations, scale)

    def set_toybox(self, visible):
        self._toybox_on = visible
        if not visible:
            self.toybox.hide()
            if self.pet.ball is not None and self.pet.ball.home == "box":
                self.pet.put_ball_away()

    def _play_from_toybox(self, x):
        """La pelote bondit hors de la boîte, vers le chat."""
        self.pet.toss_ball(x, self.toybox.floor_y - self.toybox.height() * 0.6, home="box")

    def _ball_thrown(self, vx, vy):
        """Pelote lâchée à la souris : rangée si on la pose sur sa boîte, sinon lancée."""
        ball = self.pet.ball
        box = self.toybox
        if (ball is not None and ball.home == "box" and box.isVisible()
                and box.x() <= ball.x < box.x() + box.width() and box.y() - 20 <= ball.y <= box.y() + box.height()):
            self.pet.put_ball_away()
            return
        self.pet.throw_ball(vx, vy)

    def _toybox_home(self, snap):
        """Position enregistrée (x, sol), ou par défaut aux trois quarts du premier écran."""
        try:
            return int(self.settings.value("toybox/x")), int(self.settings.value("toybox/floor"))
        except (TypeError, ValueError):
            wa = snap.monitors[0].workarea
            try:
                return int(self.settings.value("toybox/x")), wa.bottom
            except (TypeError, ValueError):
                return wa.x + wa.w * 3 // 4, wa.bottom

    def _fit_toybox(self, snap, x, floor):
        """Pose la boîte sur le sol de l'écran qui contient (x, sol), ou du plus proche, entière."""
        wa = monitor_for(snap.monitors, x, floor - 1).workarea
        half = self.toybox.width() // 2
        x = min(max(x, wa.x + half), wa.right - half)
        self.toybox.place(x, wa.bottom)
        return x, wa.bottom

    def _toybox_dropped(self, x):
        """Fin du glisser : un seul recalage, et on enregistre exactement ce qui est affiché."""
        if self._snap is None or not self._snap.monitors:
            return
        x, floor = self._fit_toybox(self._snap, x, self.toybox.floor_y)
        self.settings.setValue("toybox/x", x)
        self.settings.setValue("toybox/floor", floor)

    def _update_toybox(self, snap):
        if not self._toybox_on or not snap.monitors:
            return
        self.toybox.set_open(self.pet.ball is not None and self.pet.ball.home == "box")  # ouverte tant que sa pelote est dehors
        if self.toybox.dragging:
            return  # pendant un glisser, la boîte suit le pointeur et rien d'autre
        # sa place enregistrée si son écran est là, sinon l'écran le plus proche (sans l'enregistrer :
        # elle y reviendra quand l'écran reviendra)
        self._fit_toybox(snap, *self._toybox_home(snap))
        if not self.toybox.isVisible():
            self.toybox.show()
            self.window.raise_()

    def set_speed(self, factor):
        self.speed = factor

    def request_quit(self):
        """Quitter : le chat sort d'abord par sa chatière."""
        if not self._quitting:
            self._quitting = True
            self.pet.leave()

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
        if self._quitting:
            self._quit_elapsed += dt
            if self.pet.gone or self._quit_elapsed > LEAVE_TIMEOUT:
                self.quit()
                return None
        dt *= self.speed
        snap = self.backend.snapshot()
        self._snap = snap
        self._update_toybox(snap)
        view = self.pet.update(dt, snap)
        if view.animation != self._last_animation:
            self._last_animation = view.animation
            log.debug("animation %s", view.animation)
        self.window.show_view(view)
        self._show_ball(view.ball)
        for event in view.events:
            self.dispatch(event)
        if self.overlay is not None:
            self.overlay.set_state(snap, self.pet)
        return view

    def _show_ball(self, ball):
        shown = self.ball_window.isVisible()
        self.ball_window.show_view(ball)
        if self.ball_window.isVisible() and not shown:
            self.window.raise_()  # le chat passe devant sa pelote

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
            ("Regarder le poisson rouge", lambda _=False: self.pet.request("fishbowl"), None),
            (status, None, None),
            None,
            ("Rester immobile", lambda on: setattr(self.pet, "still", on), self.pet.still),
            ("Sons", self.set_sound, self.sound.enabled if self.sound is not None else False),
            ("Boîte à jouets", self.set_toybox, self._toybox_on),
            ("Lancer au démarrage", autostart.set_enabled, autostart.is_enabled()),
            None,
            ("Débogage", self.toggle_debug, self.overlay is not None),
            ("À propos…", lambda _=False: self.show_about(), None),
            None,
            ("Quitter", lambda _=False: self.request_quit(), None),
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
        return (f"<b>Virtual Felix {__version__}</b> — le chat de bureau, de retour sur Linux et Windows.<br><br>"
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
        self.quitting_done = True
        self.save()
        self.timer.stop()
        if self.tray is not None:
            self.tray.hide()
        self.toybox.hide()
        self.ball_window.hide()
        self.backend.stop()
        QApplication.quit()
