"""Faim et soif du chat : jauges de 0 (repu) à 1 (affamé), qui montent avec le temps."""
from dataclasses import asdict, dataclass

MAX_CATCH_UP = 48 * 3600  # rattrapage maximal quand l'appli était fermée


@dataclass
class Needs:
    hunger: float = 0.3
    thirst: float = 0.3

    HUNGER_PER_HOUR = 0.15
    THIRST_PER_HOUR = 0.25
    THRESHOLD = 0.6

    def tick(self, seconds):
        hours = seconds / 3600.0
        self.hunger = min(1.0, self.hunger + hours * self.HUNGER_PER_HOUR)
        self.thirst = min(1.0, self.thirst + hours * self.THIRST_PER_HOUR)

    def feed(self):
        self.hunger = 0.0

    def drink(self):
        self.thirst = 0.0

    @property
    def hungry(self):
        return self.hunger >= self.THRESHOLD

    @property
    def thirsty(self):
        return self.thirst >= self.THRESHOLD

    def to_dict(self, now):
        return {**asdict(self), "saved_at": now}

    @classmethod
    def from_dict(cls, data, now):
        try:
            needs = cls(hunger=float(data["hunger"]), thirst=float(data["thirst"]))
            saved_at = float(data.get("saved_at", now))
        except (KeyError, TypeError, ValueError):
            return cls()
        needs.hunger = min(max(needs.hunger, 0.0), 1.0)
        needs.thirst = min(max(needs.thirst, 0.0), 1.0)
        needs.tick(min(max(now - saved_at, 0.0), MAX_CATCH_UP))
        return needs
