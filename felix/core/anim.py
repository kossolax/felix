"""Animations image par image."""
from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class Frame:
    sheet: int
    rect: tuple  # (x, y, w, h) dans la planche
    anchor: tuple  # (x, y) des pieds, relatif à la cellule
    under: tuple = ()  # couches dessinées dessous : ((planche, rect, (x, y) relatif à la cellule), …)
    over: tuple = ()  # … et par-dessus


def frame_bounds(frame):
    """(x0, y0, x1, y1) de l'image et de ses couches, dans les coordonnées de la cellule principale."""
    x0, y0, x1, y1 = 0, 0, frame.rect[2], frame.rect[3]
    for _sheet, rect, (ox, oy) in frame.under + frame.over:
        x0, y0 = min(x0, ox), min(y0, oy)
        x1, y1 = max(x1, ox + rect[2]), max(y1, oy + rect[3])
    return x0, y0, x1, y1


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
    enter: tuple = (0, 0)  # … et avant de la jouer (sa 1re image dessine le corps ailleurs que ses pieds)
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
