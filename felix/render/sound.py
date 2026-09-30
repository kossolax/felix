"""Sons du chat : un événement (meow, purr, crunch, lap) joue une de ses variantes WAV."""
import logging
import random
import re
from pathlib import Path

log = logging.getLogger(__name__)


def _qsound_effect(path):
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect
    effect = QSoundEffect()
    effect.setSource(QUrl.fromLocalFile(str(path)))
    effect.setVolume(0.6)
    return effect


class SoundPlayer:
    def __init__(self, directory, factory=_qsound_effect, rng=None):
        self.enabled = True
        self.rng = rng or random.Random()
        self.variants = {}
        for path in sorted(Path(directory).glob("*.wav")):
            event = re.sub(r"\d+$", "", path.stem)
            try:
                self.variants.setdefault(event, []).append(factory(path))
            except Exception:
                log.exception("son %s illisible", path.name)

    def play(self, event):
        if self.enabled and self.variants.get(event):
            self.rng.choice(self.variants[event]).play()
