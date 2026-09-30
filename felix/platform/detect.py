"""Choix du backend en deux phases : avant QApplication (plateforme Qt), puis après (backend)."""
import os
import sys


def prepare_environment(env=os.environ, platform=sys.platform):
    """Phase 1 : renvoie 'windows', 'x11' ou 'wayland'. Sous Wayland, force XWayland."""
    if platform == "win32":
        return "windows"
    if env.get("WAYLAND_DISPLAY") or env.get("XDG_SESSION_TYPE") == "wayland":
        env.setdefault("QT_QPA_PLATFORM", "xcb")  # placement absolu et premier plan
        return "wayland"
    return "x11"


def choose_backend(session, requested="auto", helper_available=False):
    """Phase 2 : nom du backend à utiliser."""
    if requested != "auto":
        return requested
    if session == "windows":
        return "windows"
    if helper_available:
        return "gnome_shell"
    return "x11" if session == "x11" else "degraded"


class BackendUpgrader:
    """Remplace le backend dégradé par celui de l'extension GNOME dès qu'elle apparaît."""

    def __init__(self, check, factory):
        self.check = check
        self.factory = factory
        self.done = False

    def poll(self, current):
        if self.done or not self.check():
            return None
        try:
            new = self.factory()
        except Exception:
            import logging
            logging.getLogger("felix").exception("passage au backend GNOME impossible")
            return None
        current.stop()
        self.done = True
        return new
