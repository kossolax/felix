"""Récupère en arrière-plan les extensions de Felix II qui manquent (le chat vit pendant ce temps)."""
import threading

from PySide6.QtCore import QObject, Signal


class ExtensionFetcher(QObject):
    finished = Signal(list, list)  # extensions installées, erreurs (reçu dans le fil de l'interface)

    def __init__(self, install):
        super().__init__()
        self._install = install  # () -> (installées, erreurs)

    def start(self):
        threading.Thread(target=self._run, name="felix-extensions", daemon=True).start()

    def _run(self):
        try:
            installed, errors = self._install()
        except Exception as exc:  # jamais d'exception perdue dans un fil
            installed, errors = [], [str(exc)]
        self.finished.emit(list(installed), list(errors))
