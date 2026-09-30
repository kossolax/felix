"""Animations image par image."""
from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class Frame:
    sheet: int
    rect: tuple  # (x, y, w, h) dans la planche
    anchor: tuple  # (x, y) des pieds, relatif à la cellule


@dataclass(frozen=True)
class Animation:
    name: str
    sheet: int
    frames: tuple
    fps: float = 10
    loop: bool = False
    dx: float = 0  # déplacement horizontal par image
    facing: str = "front"
    shift: tuple = (0, 0)  # déplacement de la position une fois l'animation finie
    marks: tuple = ()  # ((rect dans la planche), (x, y) dans la cellule) : traces laissées à la fin


class Player:
    def __init__(self, animation):
        self.animation = animation
        self.index = 0
        self.finished = False
        self._acc = 0.0

    @property
    def frame(self):
        return self.animation.frames[self.index]

    def update(self, dt):
        """Avance le temps ; renvoie le nombre d'images passées."""
        anim = self.animation
        period = 1.0 / anim.fps
        self._acc += dt
        steps = 0
        while not self.finished and self._acc + EPS >= period:
            self._acc -= period
            if self.index < len(anim.frames) - 1:
                self.index += 1
                steps += 1
            elif anim.loop:
                self.index = 0
                steps += 1
            else:
                self.finished = True
        return steps
