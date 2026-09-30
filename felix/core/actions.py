"""Actions des scripts du chat : chacune tourne jusqu'à sa fin (update renvoie True), puis le
script reprend. Voir felix.core.pet."""
import math
from dataclasses import dataclass

from felix.core.anim import Frame
from felix.core.physics import GRAVITY, step
from felix.core.surfaces import support_at
from felix.core.tuning import (
    EDGE_MARGIN, JUMP_APEX, ATTENTION, PAW_RANGE, WATCH_PATIENCE, WATCH_MAX, BORED_AFTER, CLIMB_SPEED,
    CLIMB_LIFT, CLIMB_TOP_DROP, BALL_LAUNCH, OUTING_ROOM,
)


@dataclass
class BallView:
    x: float
    y: float
    frame: int
    visible: bool = True  # cachée quand les images du chat la dessinent elles-mêmes
    anim: str = "yarn_ball"  # images de la balle (pelote, ballon…)
    grabbable: bool = True


@dataclass
class View:
    animation: str
    frame: Frame
    x: float
    y: float
    mirrored: bool = False
    hidden: bool = False
    events: tuple = ()  # sons à jouer : meow, purr, crunch, lap…
    ball: BallView = None
    treats: tuple = ()  # friandises tombées (BallView)
    kitten: BallView = None  # le chaton, quand il vit seul


def direction_to(hx, hy, cx, cy):
    """Direction du curseur vue depuis la tête : up, left, right, bottom_left, bottom_right."""
    dx, dy = cx - hx, cy - hy
    if dy < 0 and -dy > abs(dx) * 1.5:
        return "up"
    if dy > 0 and dy > abs(dx) * 0.6:
        return "bottom_left" if dx < 0 else "bottom_right"
    return "left" if dx < 0 else "right"


# --- Actions -----------------------------------------------------------------

class Play:
    """Joue une animation : une fois, ou pendant `duration` secondes si elle boucle.

    `idle` : l'attente s'arrête si le curseur s'approche.
    `slide` : déplacement du chat réparti sur l'animation (pour se recaler en s'asseyant).
    """
    airborne = False

    def __init__(self, name, duration=None, mirrored=False, idle=False, event=None, slide=0.0):
        self.name = name
        self.duration = duration
        self.mirrored = mirrored
        self.idle = idle
        self.event = event
        self.slide = slide

    def start(self, pet):
        pet.play(self.name, self.mirrored)
        self.elapsed = 0.0
        self.frames = 0
        self.slid = 0.0
        if self.event:
            pet.emit(self.event)

    def _slide(self, pet, fraction):
        step = self.slide * min(fraction, 1.0) - self.slid
        pet.body.x += step
        self.slid += step

    def update(self, pet, dt):
        if self.idle and pet.cursor_near():
            return True
        self.frames += pet.player.update(dt)
        self.elapsed += dt
        anim = pet.player.animation
        if self.slide:
            self._slide(pet, self.elapsed * anim.fps / len(anim.frames))
        if self.duration is not None:
            return self.elapsed >= self.duration
        if anim.loop:
            return self.frames >= len(anim.frames)
        if pet.player.finished:
            if self.slide:
                self._slide(pet, 1.0)
            if anim.marks:
                pet.emit(("marks", pet.marks_on_screen(anim)))
            pet.shift(anim.shift)
            return True
        return False


class Hold(Play):
    """Reste figé sur une image d'une animation."""

    def __init__(self, name, index, duration, idle=True, event=None):
        super().__init__(name, duration, idle=idle, event=event)
        self.index = index

    def start(self, pet):
        super().start(pet)
        pet.player.index = self.index if self.index >= 0 else len(pet.player.animation.frames) + self.index

    def update(self, pet, dt):
        if self.idle and pet.cursor_near():
            return True
        self.elapsed += dt
        return self.elapsed >= self.duration


class WalkTo:
    airborne = False

    def __init__(self, x, idle=True, gait="walk", margin=EDGE_MARGIN):
        self.target = x
        self.idle = idle
        self.gait = gait  # walk, ou trot (plus pressé)
        self.margin = margin  # distance minimale aux bouts de la surface

    def start(self, pet):
        self.direction = "right" if self.target > pet.body.x else "left"
        pet.play(f"{self.gait}_{self.direction}")

    def update(self, pet, dt):
        if self.idle and pet.cursor_near():
            return True
        steps = pet.player.update(dt)
        if not steps:
            return False
        dx = pet.player.animation.dx * steps
        x = pet.body.x + dx
        seg = pet.body.support
        lo, hi = seg.x0 + self.margin * pet.k, seg.x1 - self.margin * pet.k
        reached = (x >= self.target) if dx > 0 else (x <= self.target)
        if reached:
            x = self.target
        # bornée devant lui seulement : parti d'au-delà de la marge (lâché au bord), il s'en éloigne
        # sans être ramené d'un coup, et ne recule jamais
        if dx > 0:
            x = min(x, max(hi, pet.body.x))
            stop = x >= hi
        else:
            x = max(x, min(lo, pet.body.x))
            stop = x <= lo
        pet.body.x = x
        return reached or stop


class Watch:
    """Assis, suit le curseur de la tête. Finit si le curseur part (reason='gone'),
    s'approche à portée de patte ('paw'), ou au bout de WATCH_MAX ('bored')."""
    airborne = False

    def start(self, pet):
        self.reason = None
        self.direction = None
        self.away = 0.0
        self.elapsed = 0.0
        pet.play("head_ambient")

    def update(self, pet, dt):
        self.elapsed += dt
        pet.player.update(dt)
        if pet.cursor_idle >= BORED_AFTER:
            self.reason = "bored"
            return True
        cursor = pet.snap.cursor
        hx, hy = pet.head()
        dist = math.hypot(cursor[0] - hx, cursor[1] - hy) if cursor else float("inf")
        if dist > ATTENTION:
            self.away += dt
            if self.away >= WATCH_PATIENCE:
                self.reason = "gone"
                return True
            return False
        self.away = 0.0
        self.direction = direction_to(hx, hy, *cursor)
        if dist <= PAW_RANGE * pet.k:
            self.reason = "paw"
            return True
        name = f"head_{self.direction}"
        if pet.player.animation.name != name:
            pet.play(name)
        if self.elapsed >= WATCH_MAX:
            self.reason = "bored"
            return True
        return False


def _window_under(pet, owner):
    """Fenêtre `owner` si elle existe encore et se trouve sous le chat, sinon None."""
    win = next((w for w in pet.snap.windows if w.id == owner), None)
    if win is None or not (win.rect.x <= pet.body.x < win.rect.right):
        return None
    return win


class Away:
    """Le chat est sorti par sa chatière : invisible pendant `duration`, ou jusqu'à ce qu'on le demande.

    Au retour, il réapparaît sur le sol de l'écran où il était."""
    airborne = True  # pas de physique pendant l'absence

    def __init__(self, duration):
        self.duration = duration

    def start(self, pet):
        self.elapsed = 0.0
        pet.away = True

    def update(self, pet, dt):
        self.elapsed += dt
        if self.elapsed < self.duration and not pet._requests:
            return False
        pet.away = False
        floors = [s for s in pet.segments if s.owner is None]
        floor = min(floors, key=lambda s: 0 if s.x0 <= pet.body.x < s.x1 else min(abs(s.x0 - pet.body.x),
                                                                                   abs(s.x1 - pet.body.x)))
        margin = OUTING_ROOM[1] * pet.k
        x = min(max(pet.body.x, floor.x0 + margin), max(floor.x0 + margin, floor.x1 - margin))
        pet.body.x, pet.body.y, pet.body.support, pet.body.owner_rect = x, floor.y, floor, None
        return True


class Climb:
    """Escalade la face d'une fenêtre jusqu'à son bord (pieds CLIMB_TOP_DROP sous le bord).

    Suit la fenêtre si elle bouge ; si elle disparaît, le chat tombe."""
    airborne = True

    def __init__(self, owner):
        self.owner = owner

    def start(self, pet):
        pet.body.support = None
        pet.body.y -= CLIMB_LIFT * pet.k
        self.bottom = pet.body.y
        pet.play("climb")

    def update(self, pet, dt):
        win = _window_under(pet, self.owner)
        if win is None:
            pet._start_fall()
            return False
        pet.player.update(dt)
        target = win.rect.y + CLIMB_TOP_DROP * pet.k
        pet.body.y = max(target, pet.body.y - CLIMB_SPEED * pet.k * dt)
        if pet.body.y > target:
            return False
        pet.emit(("claws", pet.body.x, win.rect.y + CLIMB_TOP_DROP * pet.k // 2, self.bottom))
        return True


class ClimbTop:
    """Se hisse sur le bord et s'y assoit (de dos)."""
    airborne = True

    def __init__(self, owner):
        self.owner = owner

    def start(self, pet):
        win = _window_under(pet, self.owner)
        if win is not None:
            pet.body.y = win.rect.y
        pet.play("climb_top")

    def update(self, pet, dt):
        win = _window_under(pet, self.owner)
        if win is None:
            pet._start_fall()
            return False
        pet.body.y = win.rect.y
        pet.player.update(dt)
        if not pet.player.finished:
            return False
        seg = support_at(pet.segments, pet.body.x, pet.body.y, owner=self.owner)
        if seg is None:  # bord caché par une autre fenêtre entre-temps
            pet._start_fall()
            return False
        pet.body.support = seg
        pet.body.owner_rect = win.rect
        pet.shift(pet.player.animation.shift)
        self.airborne = False
        return True


class Jump:
    def __init__(self, x, y, prep=None):
        self.target = (x, y)
        self.prep = prep  # élan (par défaut jump_prep_<direction>)
        self.airborne = False

    def start(self, pet):
        self.direction = "right" if self.target[0] >= pet.body.x else "left"
        pet.facing = self.direction
        pet.play(self.prep or f"jump_prep_{self.direction}")
        self.phase = "prep"

    def _launch(self, pet):
        body = pet.body
        tx, ty = self.target
        apex = min(body.y, ty) - JUMP_APEX
        vy = -math.sqrt(2 * GRAVITY * (body.y - apex))
        t = -vy / GRAVITY + math.sqrt(2 * (ty - apex) / GRAVITY)
        body.vx, body.vy, body.support = (tx - body.x) / t, vy, None
        self.airborne = True
        pet.play(f"jump_air_{self.direction}")
        self.phase = "air"

    def update(self, pet, dt):
        pet.player.update(dt)
        if self.phase == "prep":
            if pet.player.finished:
                self._launch(pet)
            return False
        if self.phase == "air":
            step(pet.body, dt, pet.snap, pet.segments)
            if pet.body.grounded:
                self.airborne = False
                pet.play(f"jump_land_{self.direction}")
                self.phase = "land"
            return False
        return pet.player.finished


class WatchBall:
    """Debout, suit la pelote des yeux (et se retourne si elle passe derrière lui).

    until : 'free' (posée et lâchée), 'rest' (arrêtée), 'gone' (partie), 'near' (à moins de `near`
    px de lui, sur sa surface) ou 'never' (juste la regarder) ; `ok` : c'est arrivé avant la fin
    de la patience. `pose` : une animation en boucle à jouer à la place (sans se retourner)."""
    airborne = False

    def __init__(self, limit, until="free", near=0.0, pose=None, mirrored=False):
        self.limit = limit
        self.until = until
        self.near = near
        self.pose = pose
        self.mirrored = mirrored

    def start(self, pet):
        self.elapsed = 0.0
        self.ok = False
        if self.pose:
            pet.play(self.pose, self.mirrored)
        else:
            pet.play(f"stand_{pet.facing}")

    def _met(self, ball):
        if self.until == "gone":
            return ball is None
        if ball is None:
            return False
        if self.until == "free":
            return ball.grounded and not ball.held
        return self.until == "rest" and ball.resting

    def update(self, pet, dt):
        ball = pet.ball
        if (self.until == "near" and ball is not None and ball.support == pet.body.support
                and abs(ball.x - pet.body.x) <= self.near):
            self.ok = True
            return True
        self.elapsed += dt
        pet.player.update(dt)
        if self._met(ball):
            self.ok = True
            return True
        if ball is None:
            return True
        name = pet.player.animation.name
        if name.startswith("turn_to_"):
            if pet.player.finished:
                pet.play(f"stand_{pet.facing}")
        elif not self.pose:
            want = "right" if ball.x >= pet.body.x else "left"
            if want != pet.facing and abs(ball.x - pet.body.x) > 10:
                pet.play(f"turn_to_{want}")  # il se retourne, sans pivoter d'un coup
        return self.elapsed >= self.limit


class Chase:
    """Trotte derrière la pelote qui roule jusqu'à la place à côté d'elle ; s'arrête aussi quand elle
    s'arrête, rebondit, change de surface ou qu'on la prend."""
    airborne = False

    def __init__(self, side):
        self.side = side  # côté du chat où elle sera

    def start(self, pet):
        self.direction = pet.facing
        pet.play(f"trot_{self.direction}")

    def update(self, pet, dt):
        ball = pet.ball
        seg = pet.body.support
        if ball is None or ball.held or ball.resting or ball.support != seg:
            return True
        target = ball.x - self.side * ball.kind.at_feet * pet.k
        sign = 1 if self.direction == "right" else -1
        if (target - pet.body.x) * sign <= 0:
            return True
        steps = pet.player.update(dt)
        if not steps:
            return False
        x = pet.body.x + pet.player.animation.dx * steps
        lo, hi = seg.x0 + EDGE_MARGIN * pet.k, seg.x1 - EDGE_MARGIN * pet.k
        reached = (x - target) * sign >= 0
        pet.body.x = min(max(target if reached else x, lo), hi)
        return reached or pet.body.x in (lo, hi)


class Bat(Play):
    """Coup de patte assis : à partir de l'image `launch` de l'animation, la vraie balle repart
    de sous la patte, à `offset` px des pieds (la planche ne la dessine plus à partir de là)."""

    def __init__(self, side, speed, hop, away=False, name="yarn_bat"):
        super().__init__(name, mirrored=side < 0)
        self.side, self.speed, self.hop, self.away = side, speed, hop, away
        self.launch, self.offset = BALL_LAUNCH[name]
        self.kicked = False

    def update(self, pet, dt):
        done = super().update(pet, dt)
        if not self.kicked and (pet.player.index >= self.launch or done):
            self.kicked = True
            ball = pet.ball
            if ball is not None and not ball.held:
                ball.x, ball.y = pet.body.x + self.side * self.offset * pet.k, pet.body.y
                ball.support, ball.owner_rect = pet.body.support, pet.body.owner_rect
                ball.exits = self.away  # renvoyée pour de bon : elle sort de l'écran
                ball.kick(self.side * self.speed, -self.hop)
        return done
