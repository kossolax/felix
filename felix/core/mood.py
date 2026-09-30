"""Tempérament du chat (façon MoodProbability de l'original) : une énergie qui dérive lentement
et oriente ses choix, et une mémoire des dernières activités pour éviter de se répéter."""
import math
from collections import deque

ACTIVE = frozenset({"walk", "jump", "climb", "stretch", "prints", "fishbowl", "yarn", "string", "hunt", "outing", "edge",
                    "beachball", "mouse", "frog"})
CALM = frozenset({"sit", "sit_back", "doze", "wash", "stand", "tv"})  # (réclamer à manger ne dépend pas de l'humeur)
RECENT = 3
RECENT_FACTORS = (0.1, 0.3, 0.6)  # dernière activité, avant-dernière, …
SPEND, REST = 0.04, 0.03  # énergie dépensée / récupérée par activité
TARGET = 0.55  # l'énergie revient doucement vers cette valeur
REVERT_TIME = 1800.0  # s
NOISE = 0.003  # écart-type de la dérive par seconde


class Temperament:
    def __init__(self, rng, energy=0.6, drift=True):
        self.rng = rng
        self.energy = energy
        self.drift = drift
        self.recent = deque(maxlen=RECENT)

    def tick(self, dt):
        if not self.drift:
            return
        self.energy += (TARGET - self.energy) * dt / REVERT_TIME + self.rng.gauss(0.0, NOISE * math.sqrt(dt))
        self.energy = min(max(self.energy, 0.0), 1.0)

    def weights(self, base):
        lively = 0.2 + 1.6 * self.energy
        tired = 0.2 + 1.6 * (1.0 - self.energy)
        out = {}
        for name, w in base.items():
            if name in ACTIVE:
                w *= lively
            elif name in CALM:
                w *= tired
            for age, previous in enumerate(reversed(self.recent)):
                if previous == name:
                    w *= RECENT_FACTORS[age]
            out[name] = w
        if len(self.recent) >= 2 and self.recent[-1] == self.recent[-2] and len(out) > 1:
            out[self.recent[-1]] = 0.0  # jamais trois fois de suite
        return out

    def pick(self, base):
        weights = self.weights(base)
        name = self.rng.choices(list(weights), weights=list(weights.values()))[0]
        self.did(name)
        return name

    def did(self, name):
        self.recent.append(name)
        if name in ACTIVE:
            self.energy = max(0.0, self.energy - SPEND)
        elif name in CALM:
            self.energy = min(1.0, self.energy + REST)
