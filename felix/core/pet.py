"""Cerveau du chat : scripts d'actions, physique et interactions avec la souris.

Un script est un générateur qui produit des actions (Play, WalkTo, Jump…).
Chaque action tourne jusqu'à sa fin, puis le script reprend. La chute et la
prise à la souris interrompent le script en cours ; les actions d'attente
s'interrompent quand le curseur s'approche.
"""
import math
import random
from dataclasses import dataclass

from felix.core.anim import Frame, Player
from felix.core.ball import BALL_RADIUS, Ball
from felix.core.mood import Temperament
from felix.core.needs import Needs
from felix.core.physics import GRAVITY, Body, step
from felix.core.surfaces import compute_surfaces, monitor_for, support_at

EDGE_MARGIN = 30
JUMP_UP = 650
JUMP_DOWN = 700
JUMP_REACH = 500
JUMP_APEX = 70
SCARED_FALL = 400
HEAD_HEIGHT = 60  # hauteur de la tête au-dessus des pieds, chat assis
ATTENTION = 220  # distance tête-curseur qui attire l'attention
PAW_RANGE = 90  # distance tête-curseur pour un coup de patte
WATCH_PATIENCE = 1.5  # secondes sans curseur avant de reprendre sa vie
WATCH_MAX = 30
HUNT_MIN, HUNT_MAX = 200, 800  # distance horizontale d'une proie au sol
HUNT_LEVEL = 120  # le curseur doit être posé à moins de ça au-dessus de la surface
HUNT_APPROACH = 150
HUNT_CHANCE = 0.5
HUNT_COOLDOWN = 20.0
BORED_AFTER = 8.0  # un curseur immobile depuis ce temps n'intéresse plus
PREY_FRESH = 20.0  # une proie immobile depuis plus longtemps n'est plus chassée
CURSOR_JITTER = 3
FEED_ROOM = (45, 110)  # place nécessaire à gauche / à droite du chat pour le placard
DRINK_ROOM = (80, 125)  # … pour la bouteille de lait
EAT_TIME = 4.0
PRINTS_ROOM = (65, 50)
FISHBOWL_ROOM = (35, 50)
TV_ROOM = (45, 45)
YARN_ROOM = (30, 200)  # place pour bondir sur la pelote pendue à sa ficelle
TV_TIME = (12, 25)
CLIMB_SPEED = 70.0  # px/s
CLIMB_LIFT = 24  # le chat quitte le sol en se dressant contre la vitre
CLIMB_TOP_DROP = 69  # pieds du chat accroché, sous le bord, au début de climb_top
CLIMB_MIN = 120  # une fenêtre moins haute que ça au-dessus du chat : on saute
BALL_AT_FEET = 38  # px entre les pieds du chat assis et la pelote que dessinent yarn_sniff / yarn_pat
BAT_FROM = 44  # … et celle de la 2e image de yarn_bat, d'où la vraie pelote repart
BAKED_BALL = frozenset({"yarn_sniff", "yarn_pat", "yarn_unroll", "yarn_follow", "yarn_bat_away"})  # pelote dessinée
BAT_SPEED = (160, 460)  # px/s
AWAY_SPEED = (380, 560)  # dernier coup de patte, quand la place manque pour le final d'origine
BAT_HOP = (0, 380)  # px/s vers le haut
BALL_ROUNDS = (4, 7)  # tours de jeu ; le dernier finit par le final d'origine (elle se déroule et s'en va)
PAT_ROUNDS = (1, 3)
BALL_CATCH = 30  # px : la pelote est « aux pieds » (il se recale en s'asseyant)
POUNCE_RANGE = (90, 320)  # px : distance d'où il bondit sur la pelote
POUNCE_CHANCE = 0.6
BAT_ROOM = 400  # px : place qu'il veut devant la pelote pour la renvoyer sans faire le tour
LEAP_RUNUP = 180  # px : élan avant de sauter vers une pelote posée sur une autre surface
BALL_PATIENCE = 12.0  # s : attend qu'on lâche la pelote ou qu'elle retombe
REACH_TRIES = 12
FINALE_ROOM = 200  # place pour yarn_unroll … yarn_bat_away
DANGLE_BALL = (14, 28)  # pelote au bout de sa ficelle, dans la cellule de yarn_dangle
TOSS_HEIGHT = 260  # px : lancée d'un bord de l'écran, à cette hauteur au-dessus du chat
TOSS_SPEED = (350, 600)
TOSS_WATCH = 5.0
BOX_HOP_X = (120, 240)  # sortie de la boîte, vers le chat
BOX_HOP_Y = (420, 560)
BALL_OUT_WEIGHT = 20  # envie de jouer avec une pelote qui traîne
AWAY_TIME = (60, 300)  # s dehors, après une sortie par la chatière
OUTING_ROOM = (30, 110)


@dataclass
class BallView:
    x: float
    y: float
    frame: int
    visible: bool = True  # cachée quand les images du chat la dessinent elles-mêmes


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

    def __init__(self, x, idle=True, gait="walk"):
        self.target = x
        self.idle = idle
        self.gait = gait  # walk, ou trot (plus pressé)

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
        lo, hi = seg.x0 + EDGE_MARGIN * pet.k, seg.x1 - EDGE_MARGIN * pet.k
        reached = (x >= self.target) if dx > 0 else (x <= self.target)
        if reached:
            x = self.target
        pet.body.x = min(max(x, lo), hi)
        return reached or pet.body.x in (lo, hi)


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

    until : 'free' (posée et lâchée), 'rest' (arrêtée), 'gone' (partie) ou 'never' (juste la
    regarder) ; `ok` : c'est arrivé avant la fin de la patience."""
    airborne = False

    def __init__(self, limit, until="free"):
        self.limit = limit
        self.until = until

    def start(self, pet):
        self.elapsed = 0.0
        self.ok = False
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
        self.elapsed += dt
        pet.player.update(dt)
        ball = pet.ball
        if self._met(ball):
            self.ok = True
            return True
        if ball is None:
            return True
        want = "right" if ball.x >= pet.body.x else "left"
        if want != pet.facing and abs(ball.x - pet.body.x) > 10:
            pet.play(f"stand_{want}")
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
        target = ball.x - self.side * BALL_AT_FEET * pet.k
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
    """Coup de patte assis : à la 2e image, la vraie pelote repart de sous la patte (la planche
    ne la dessine plus à partir de là)."""

    def __init__(self, side, speed, hop, away=False):
        super().__init__("yarn_bat", mirrored=side < 0)
        self.side, self.speed, self.hop, self.away = side, speed, hop, away
        self.kicked = False

    def update(self, pet, dt):
        done = super().update(pet, dt)
        if not self.kicked and (pet.player.index >= 1 or done):
            self.kicked = True
            ball = pet.ball
            if ball is not None and not ball.held:
                ball.x, ball.y = pet.body.x + self.side * BAT_FROM * pet.k, pet.body.y
                ball.support, ball.owner_rect = pet.body.support, pet.body.owner_rect
                ball.exits = self.away  # renvoyée pour de bon : elle sort de l'écran
                ball.kick(self.side * self.speed, -self.hop)
        return done


# --- Le chat -------------------------------------------------------------------

BEHAVIORS = {
    "walk": 30, "stand": 20, "sit": 14, "sit_back": 5, "wash": 8, "stretch": 5, "jump": 18, "doze": 3,
}
BEG_WEIGHT = 30
MISCHIEF = {"prints": 3, "fishbowl": 2, "tv": 1, "yarn": 1, "outing": 1}
CLIMB_WEIGHT = 10


class Pet:
    def __init__(self, animations, rng=None, needs=None, scale=1):
        self.anims = animations
        self.k = scale  # taille du chat : les distances liées à son corps suivent
        self.rng = rng or random.Random()
        self.needs = needs if needs is not None else Needs()
        self.temper = Temperament(self.rng)
        self._events = []
        self._requests = []
        self.ball = None  # pelote de laine libre, quand elle est sortie
        self.scene = None  # soin en cours ('feed', 'drink') : pas interrompu par une autre commande
        self.gone = False  # sorti par la chatière (on peut fermer l'appli)
        self.away = False  # parti se promener dehors (invisible)
        self.body = None
        self.facing = "right"
        self.mode = "script"
        self.player = None
        self.mirrored = False
        self.script = None
        self.action = None
        self.snap = None
        self.segments = []
        self._still = False
        self._pointer = None
        self._grab_offset = (0, 0)
        self._fall_from = 0.0
        self.clock = 0.0
        self.cursor_idle = 0.0  # secondes depuis le dernier mouvement du curseur
        self._last_cursor = None
        self._next_hunt = 0.0

    # -- animation --
    def set_animations(self, animations, scale):
        """Changement de taille à chaud : mêmes animations, autre échelle."""
        self.anims = animations
        self.k = scale
        if self.ball is not None:
            self.ball.k = scale
        if self.player is not None:
            index = self.player.index
            self.player = Player(animations[self.player.animation.name])
            self.player.index = min(index, len(self.player.animation.frames) - 1)

    def play(self, name, mirrored=False):
        anim = self.anims[name]
        self.player = Player(anim)
        self.mirrored = mirrored
        if anim.facing in ("left", "right"):
            flip = {"left": "right", "right": "left"}
            self.facing = flip[anim.facing] if mirrored else anim.facing

    def shift(self, delta):
        if delta == (0, 0) or self.body.support is None:
            return
        dx = -delta[0] if self.mirrored else delta[0]
        seg = self.body.support
        m = EDGE_MARGIN * self.k
        self.body.x = min(max(self.body.x + dx, seg.x0 + m), seg.x1 - m)

    def emit(self, event):
        self._events.append(event)

    def request(self, what):
        """Commande de l'utilisateur ('feed', 'drink', 'yarn'…). Interrompt ce que fait le chat."""
        self._requests.append(what)
        if (self.body is not None and self.scene is None and self.mode == "script"
                and not getattr(self.action, "airborne", False)):
            self._run(self._brain())

    def leave(self):
        """Le chat s'en va par sa chatière ; `gone` passe à True une fois sorti."""
        self._requests.clear()
        if (self.body is None or self.mode != "script" or not self.body.grounded
                or getattr(self.action, "airborne", False)):
            self.gone = True
            return
        self.scene = "leave"
        self._run(self._leaving())

    def _leaving(self):
        yield from self._face("right")
        yield Play("exit_flap")
        self.gone = True
        while True:
            yield Hold("exit_flap", -1, 3600, idle=False)

    # -- pelote --
    def toss_ball(self, x, y, vx=None, vy=None, home=None):
        """Sort une pelote en (x, y) (de la boîte à jouets…) : par défaut elle bondit vers le chat,
        qui vient jouer. S'il y en a déjà une dehors, il joue avec celle-là."""
        if self.ball is None:
            toward = 1 if self.body is None or self.body.x >= x else -1
            if vx is None:
                vx = toward * self.rng.uniform(*BOX_HOP_X) * self.k
            if vy is None:
                vy = -self.rng.uniform(*BOX_HOP_Y)
            self.ball = Ball(x, y, scale=self.k, home=home)
            self.ball.kick(vx, vy)
        self._want_to_play()

    def grab_ball(self):
        if self.ball is not None:
            self.ball.grab()

    def drag_ball(self, x, y):
        if self.ball is not None:
            self.ball.move_to(x, y)

    def throw_ball(self, vx, vy):
        """Pelote lâchée à la souris, avec la vitesse du geste : le chat court après."""
        if self.ball is not None:
            self.ball.throw(vx, vy)
            self._want_to_play()

    def put_ball_away(self):
        self.ball = None

    def _want_to_play(self):
        if not self._still and self.scene != "yarn" and "yarn" not in self._requests:
            self.request("yarn")

    def stroke(self):
        """Caresse (clic sans glisser) : le chat s'assoit et ronronne."""
        if self.body is not None and self.mode == "script" and self.scene is None and self.body.grounded:
            self._run(self._stroked())

    def marks_on_screen(self, anim):
        """Position écran des traces d'une animation (dernière image), avant le recalage de fin."""
        frame = anim.frames[-1]
        ax, ay = frame.anchor
        cw = frame.rect[2]
        out = []
        for sheet_rect, (mx, my) in anim.marks:
            if self.mirrored:
                x = self.body.x - (cw - ax) + (cw - mx - sheet_rect[2])
            else:
                x = self.body.x - ax + mx
            out.append(((anim.sheet, *sheet_rect), (round(x), round(self.body.y - ay + my))))
        return out

    def head(self):
        return self.body.x, self.body.y - HEAD_HEIGHT * self.k

    def cursor_near(self):
        cursor = self.snap.cursor if self.snap else None
        if cursor is None or self.body is None or not self.body.grounded or self.cursor_idle >= BORED_AFTER:
            return False
        hx, hy = self.head()
        return math.hypot(cursor[0] - hx, cursor[1] - hy) <= ATTENTION

    # -- interactions --
    @property
    def still(self):
        return self._still

    @still.setter
    def still(self, value):
        self._still = value
        if self.mode == "script" and not getattr(self.action, "airborne", False):
            self.scene = None
            self._run(self._brain())

    def grab(self, px, py):
        self.scene = None
        self.mode = "held"
        self._pointer = (px, py)
        self._grab_offset = (self.body.x - px, self.body.y - py)
        self.body.support = None
        self.body.vx = self.body.vy = 0.0
        self.action = None
        self.play(f"held_{self.facing}")

    def drag(self, px, py):
        self._pointer = (px, py)
        self.body.x, self.body.y = px + self._grab_offset[0], py + self._grab_offset[1]

    def release(self):
        self._start_fall()

    # -- boucle --
    def _track_cursor(self, dt, cursor):
        last = self._last_cursor
        moved = cursor is not None and (last is None or abs(cursor[0] - last[0]) + abs(cursor[1] - last[1]) > CURSOR_JITTER)
        if moved:
            self._last_cursor = cursor
            self.cursor_idle = 0.0
        else:
            self.cursor_idle += dt

    def update(self, dt, snap):
        self.snap = snap
        self.clock += dt
        self._track_cursor(dt, snap.cursor)
        self.segments = compute_surfaces(snap)
        if self.body is None:
            self._spawn()
        self.needs.tick(dt)
        self.temper.tick(dt)
        hidden = self.away or self._fullscreen_at(snap, self.body.x, self.body.y - 1)
        if self.away:
            self._advance(dt)  # le temps passe dehors aussi
        elif not hidden:
            self._update(dt)
        ball = self._update_ball(dt, snap)
        events, self._events = tuple(self._events), []
        return View(self.player.animation.name, self.player.frame, self.body.x, self.body.y,
                    self.mirrored, hidden, events, ball)

    def _update_ball(self, dt, snap):
        ball = self.ball
        if ball is None:
            return None
        ball.update(dt, snap, self.segments)
        if ball.gone:
            self.ball = None
            return None
        name = self.player.animation.name
        drawn = name in BAKED_BALL or (name == "yarn_bat" and self.player.index == 0)
        return BallView(ball.x, ball.y, ball.frame, not drawn and not self._fullscreen_at(snap, ball.x, ball.y - 1))

    def _fullscreen_at(self, snap, x, y):
        """La fenêtre du dessus, sur l'écran de (x, y), est-elle en plein écran (vidéo, jeu…) ?"""
        mons = [m.geometry for m in snap.monitors]
        if not mons or not snap.windows:
            return False
        mon = next((g for g in mons if g.contains(x, y)), None) or min(mons, key=lambda g: g.distance2(x, y))
        for w in snap.windows:
            r = w.rect
            if r.x < mon.right and mon.x < r.right and r.y < mon.bottom and mon.y < r.bottom:
                return w.fullscreen
        return False

    def _update(self, dt):
        if self.mode == "held":
            self.player.update(dt)
            return
        if self.mode == "falling":
            self.player.update(dt)
            step(self.body, dt, self.snap, self.segments)
            if self.body.grounded:
                self.mode = "script"
                self._run(self._landed(self.body.y - self._fall_from))
            return
        if not getattr(self.action, "airborne", False):
            step(self.body, dt, self.snap, self.segments)
            if not self.body.grounded:
                self._start_fall()
                return
        self._advance(dt)

    def _advance(self, dt):
        if self.action is None or self.action.update(self, dt):
            self.action = next(self.script)
            self.action.start(self)

    def _run(self, script):
        self.script = script
        self.action = next(self.script)
        self.action.start(self)

    def _start_fall(self):
        self.scene = None
        self.mode = "falling"
        self.action = None
        self._fall_from = self.body.y
        self.body.support = None
        self.play(f"fall_{self.facing}")

    def _spawn(self):
        floors = [s for s in self.segments if s.owner is None]
        floor = floors[0]
        x = self.rng.uniform(floor.x0 + 100, max(floor.x0 + 101, floor.x1 - 100))
        self.body = Body(x=x, y=floor.y, support=floor)
        self._run(self._enter())

    # -- scripts --
    def _enter(self):
        yield Play("enter_flap")
        yield from self._brain()

    def _landed(self, height):
        yield Play(f"land_{self.facing}")
        if height > SCARED_FALL:
            yield Play(f"scared_{self.facing}")
        yield from self._brain()

    def _brain(self):
        while True:
            if self._requests:
                self.scene = self._requests.pop(0)
                yield from getattr(self, f"_do_{self.scene}")()
                self.scene = None
                continue
            if self._still:
                yield Play(f"stand_{self.facing}", duration=1.0)
                continue
            if self.cursor_near():
                yield from self._do_watch()
                continue
            prey = self._prey()
            if prey is not None and self.rng.random() < HUNT_CHANCE:
                self.temper.did("hunt")
                yield from self._do_hunt(prey)
                continue
            choices = dict(BEHAVIORS)
            choices.update(MISCHIEF)
            if self._ball_to_play_with():
                choices["yarn"] = BALL_OUT_WEIGHT
            if self.needs.hungry or self.needs.thirsty:
                choices["beg"] = BEG_WEIGHT * (1 + 2 * max(self.needs.hunger, self.needs.thirst))
            targets = self._jump_targets()
            if not targets:
                choices.pop("jump")
            if self._climb_target() is not None:
                choices["climb"] = CLIMB_WEIGHT
            name = self.temper.pick(choices)
            if name == "jump":
                yield from self._do_jump(targets)
            else:
                yield from getattr(self, f"_do_{name}")()

    def _face(self, direction):
        if self.facing != direction:
            yield Play(f"turn_to_{direction}")

    def _do_walk(self):
        seg = self.body.support
        m = EDGE_MARGIN * self.k
        target = self.rng.uniform(seg.x0 + m, max(seg.x0 + m, seg.x1 - m))
        if abs(target - self.body.x) < 20:
            return
        yield from self._face("right" if target > self.body.x else "left")
        yield WalkTo(target)

    def _do_stand(self):
        yield Play(f"stand_{self.facing}", duration=self.rng.uniform(2, 6), idle=True)

    def _do_sit(self):
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("sit_front", duration=self.rng.uniform(4, 12), idle=True)
        yield Play("sit_up")

    def _do_sit_back(self):
        yield from self._face("right")
        yield Play("sit_back_down")
        yield Play("sit_back", duration=self.rng.uniform(4, 10), idle=True)
        yield Play("sit_back_up")

    def _do_wash(self):
        yield Play("wash")

    def _do_stretch(self):
        yield from self._face("right")
        yield Play("stretch")

    def _do_doze(self):
        yield from self._face("right")
        yield Play("sit_down")
        yield Hold("sit_front", 0, self.rng.uniform(10, 25))
        yield Play("sit_up")

    def _stroked(self):
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("sit_front", duration=3.5, event="purr")
        yield Play("sit_up")
        yield from self._brain()

    def _do_outing(self):
        yield from self._make_room(*OUTING_ROOM)
        yield from self._face("right")
        yield Play("exit_flap")
        yield Away(self.rng.uniform(*AWAY_TIME))
        yield Play("enter_flap")

    def _do_beg(self):
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("sit_front", duration=3.0, idle=True, event="meow")
        yield Play("sit_up")

    def _make_room(self, left, right):
        seg = self.body.support
        lo, hi = seg.x0 + left * self.k, seg.x1 - right * self.k
        target = min(max(self.body.x, lo), hi) if lo <= hi else (seg.x0 + seg.x1) / 2
        if abs(target - self.body.x) > 5:
            yield from self._face("right" if target > self.body.x else "left")
            yield WalkTo(target, idle=False)

    def _do_feed(self):
        yield from self._make_room(*FEED_ROOM)
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("cupboard_enter")
        yield Hold("cupboard_enter", -1, EAT_TIME, idle=False, event="crunch")
        self.needs.feed()
        yield Play("cupboard_exit")
        yield Play("cupboard_leave")

    def _do_drink(self):
        yield from self._make_room(*DRINK_ROOM)
        yield from self._face("right")
        yield Play("milk_arrive")
        yield Play("milk_peek")
        yield Play("milk_around")
        yield Play("milk_spill")
        yield Play("milk_drink", event="lap")
        self.needs.drink()

    def _do_prints(self):
        yield from self._make_room(*PRINTS_ROOM)
        yield from self._face("right")
        yield Play("paw_prints")

    def _do_fishbowl(self):
        yield from self._make_room(*FISHBOWL_ROOM)
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("fishbowl")
        yield Play("sit_up")

    def _do_tv(self):
        yield from self._make_room(*TV_ROOM)
        yield from self._face("right")
        yield Play("sit_back_down")
        yield Play("tv_on")
        yield Play("tv_watch", duration=self.rng.uniform(*TV_TIME), event="purr")
        yield Play("tv_off")
        yield Play("sit_back_tv", duration=1.5)
        yield Play("tv_leave")

    def _do_yarn(self):
        """Partie de pelote. Elle arrive d'un bord de l'écran ou pend à sa ficelle (sauf si elle est
        déjà dehors) ; le chat la guette, la rattrape ou bondit dessus, la tapote et la renvoie d'un
        coup de patte, plusieurs fois ; au dernier tour, elle se déroule et s'en va (final d'origine)."""
        if self.ball is None:
            yield from self._ball_arrives()
        rounds = self.rng.randint(*BALL_ROUNDS)
        for i in range(rounds):
            side = yield from self._reach_ball()
            if side is None:
                return  # partie, hors d'atteinte, ou on ne la lui rend pas
            yield from self._play_at_feet(side, last=i == rounds - 1)

    def _ball_arrives(self):
        if self.rng.random() < 0.5:
            # pendue au bout de sa ficelle : le chat bondit l'attraper, et elle tombe
            yield from self._make_room(*YARN_ROOM)
            yield from self._face("right")
            x, y = self.body.x, self.body.y
            yield Play("string_leap")
            frame = self.anims["string_leap"].frames[-1]
            _sheet, _rect, (ox, oy) = frame.under[0]
            self.ball = Ball(x - frame.anchor[0] + ox + DANGLE_BALL[0] * self.k,
                             y - frame.anchor[1] + oy + DANGLE_BALL[1] * self.k, scale=self.k)
            self.ball.kick(self.rng.uniform(150, 260) * self.k, 0)  # tirée d'un coup, elle file
            yield Play("leap_down")  # il retombe avec elle
            return
        # lancée depuis le bord le plus éloigné de l'écran : elle rebondit vers le chat
        mon = monitor_for(self.snap.monitors, self.body.x, self.body.y - 1).geometry
        from_right = mon.right - self.body.x >= self.body.x - mon.x
        r = BALL_RADIUS * self.k
        speed = self.rng.uniform(*TOSS_SPEED) * self.k
        self.ball = Ball(mon.right - r if from_right else mon.x + r,
                         max(mon.y + 3 * r, self.body.y - TOSS_HEIGHT * self.k), scale=self.k)
        self.ball.kick(-speed if from_right else speed, -150)
        yield from self._face("right" if from_right else "left")
        yield WatchBall(TOSS_WATCH, until="rest")

    def _ball_to_play_with(self):
        ball = self.ball
        if ball is None or ball.held or not ball.grounded or self.body.support is None:
            return False
        return ball.support == self.body.support or self._leap_to_ball() is not None

    def _reach_ball(self):
        """Rejoint la pelote jusqu'à l'avoir aux pieds. Renvoie son côté (1 : à droite du chat,
        -1 : à gauche), ou None si elle est partie, hors d'atteinte, ou qu'on ne la lâche pas."""
        walked_closer = False
        for _ in range(REACH_TRIES):
            ball, seg = self.ball, self.body.support
            if ball is None or seg is None:
                return None
            if ball.held or not ball.grounded:
                watch = WatchBall(BALL_PATIENCE)
                yield watch
                if not watch.ok:
                    return None
                continue
            if ball.support != seg:  # sur une autre surface : y sauter, en s'approchant d'abord
                target = self._leap_to_ball()
                if target is not None:
                    yield from self._face("right" if target[0] >= self.body.x else "left")
                    yield Jump(*target)
                    continue
                m = EDGE_MARGIN * self.k
                toward = 1 if ball.x >= self.body.x else -1
                closer = min(max(ball.x - toward * LEAP_RUNUP * self.k, seg.x0 + m), seg.x1 - m)
                if walked_closer or abs(closer - self.body.x) <= 20:
                    yield WatchBall(2.0, until="never")  # la regarde, puis abandonne
                    return None
                walked_closer = True
                yield from self._face("right" if closer > self.body.x else "left")
                yield WalkTo(closer, idle=False)
                continue
            spot = self._spot_by_ball(seg)
            if spot is None:
                return None
            x, side = spot
            gap = x - self.body.x
            if abs(gap) <= BALL_CATCH * self.k:
                return side
            direction = "right" if gap > 0 else "left"
            yield from self._face(direction)
            if not ball.resting:
                yield Chase(side)
                continue
            if ((gap > 0) == (side > 0) and POUNCE_RANGE[0] * self.k <= abs(gap) <= POUNCE_RANGE[1] * self.k
                    and self.rng.random() < POUNCE_CHANCE):
                yield Play(f"stalk_{direction}")
                if self.ball is ball and ball.resting and ball.support == self.body.support:
                    yield Jump(ball.x - side * BALL_AT_FEET * self.k, seg.y, prep=f"leap_prep_{direction}")
                continue
            yield WalkTo(x, idle=False, gait="trot")
        return None

    def _spot_by_ball(self, seg):
        """Où poser les pieds pour avoir la pelote juste à côté, et de quel côté elle sera. Il la
        renverra de ce côté-là : celui d'où il arrive s'il reste de la place devant elle, sinon il
        fait le tour pour la renvoyer vers le plus grand espace libre."""
        m = EDGE_MARGIN * self.k
        near = 1 if self.ball.x >= self.body.x else -1
        spots = [(self.ball.x - side * BALL_AT_FEET * self.k, side) for side in (near, -near)]
        spots = [(x, side) for x, side in spots if seg.x0 + m <= x <= seg.x1 - m]
        if not spots:
            return None

        def room(side):
            return seg.x1 - self.ball.x if side > 0 else self.ball.x - seg.x0

        if spots[0][1] == near and room(near) >= BAT_ROOM * self.k:
            return spots[0]
        return max(spots, key=lambda spot: room(spot[1]))

    def _leap_to_ball(self):
        """Point d'atterrissage à côté d'une pelote posée sur une autre surface, si un saut y mène."""
        s = self.ball.support
        if s is None or not (self.body.y - JUMP_UP <= s.y <= self.body.y + JUMP_DOWN):
            return None
        m = EDGE_MARGIN * self.k
        near = 1 if self.ball.x >= self.body.x else -1
        for side in (near, -near):
            x = self.ball.x - side * BALL_AT_FEET * self.k
            if s.x0 + m <= x <= s.x1 - m and abs(x - self.body.x) <= JUMP_REACH:
                return x, s.y
        return None

    def _play_at_feet(self, side, last):
        """Assis à côté de la pelote : il la renifle, la tapote puis la renvoie d'un coup de patte ;
        au dernier tour, elle se déroule et s'en va (images d'origine, qui dessinent la pelote)."""
        ball = self.ball
        mirrored = side < 0
        yield from self._face("left" if mirrored else "right")
        ball.vx = 0.0  # rattrapée ; il se recale en s'asseyant pour l'avoir pile où les images la dessinent
        yield Play("sit_down", mirrored=mirrored, slide=ball.x - side * BALL_AT_FEET * self.k - self.body.x)
        spot = self.body.x + side * BALL_AT_FEET * self.k
        if self.ball is not ball or not ball.resting or abs(ball.x - spot) > 1:
            yield Play("sit_up", mirrored=mirrored)  # on la lui a prise
            return
        ball.x = spot
        mood = self.rng.random()
        if mood < 0.35:
            yield Play("yarn_sniff", mirrored=mirrored)
        if mood < 0.8:
            for _ in range(self.rng.randint(*PAT_ROUNDS)):
                yield Play("yarn_pat", mirrored=mirrored)
        if last and self._room_for_finale(side):
            for name in ("yarn_unroll", "yarn_follow", "yarn_bat_away"):
                yield Play(name, mirrored=mirrored)
            self.ball = None
            return
        speed = self.rng.uniform(*(AWAY_SPEED if last else BAT_SPEED)) * self.k
        yield Bat(side, speed, self.rng.uniform(*BAT_HOP), away=last)
        yield Play("sit_up", mirrored=mirrored)
        if last:
            yield WatchBall(BALL_PATIENCE, until="gone")

    def _room_for_finale(self, side):
        seg = self.body.support
        m = EDGE_MARGIN * self.k
        room = FINALE_ROOM * self.k
        return self.body.x + room <= seg.x1 - m if side > 0 else self.body.x - room >= seg.x0 + m

    def _climb_target(self, anywhere=False):
        """Bord de fenêtre au-dessus du chat, dont la face est devant lui (ou, si `anywhere`,
        au-dessus de n'importe quel point de sa surface)."""
        body = self.body
        support = body.support
        best = None
        for s in self.segments:
            if s.owner is None or s == support:
                continue
            if anywhere:
                if support is None or s.x1 - EDGE_MARGIN * self.k <= support.x0 or s.x0 + EDGE_MARGIN * self.k >= support.x1:
                    continue
            elif not (s.x0 + EDGE_MARGIN * self.k <= body.x < s.x1 - EDGE_MARGIN * self.k):
                continue
            if body.y - s.y < self.k * max(CLIMB_MIN, CLIMB_TOP_DROP + CLIMB_LIFT):
                continue
            if best is None or s.y > best.y:
                best = s
        return best

    def _do_climb(self):
        target = self._climb_target()
        if target is None:
            far = self._climb_target(anywhere=True)
            if far is None:
                return
            seg = self.body.support
            lo = max(far.x0, seg.x0) + EDGE_MARGIN * self.k
            hi = min(far.x1, seg.x1) - EDGE_MARGIN * self.k
            x = min(max(self.body.x, lo), hi)
            yield from self._face("right" if x > self.body.x else "left")
            yield WalkTo(x, idle=False)
            target = self._climb_target()
            if target is None:
                return
        yield from self._face("right")
        yield Play("climb_leap")
        target = self._climb_target_at(target)
        if target is None:
            return
        yield Climb(target.owner)
        yield ClimbTop(target.owner)
        yield Play("sit_back", duration=self.rng.uniform(3, 6), idle=True)
        yield Play("sit_back_up")

    def _climb_target_at(self, segment):
        """Le bord visé existe-t-il encore au-dessus du chat (fenêtre fermée ou déplacée entre-temps) ?"""
        for s in self.segments:
            if s.owner == segment.owner and s.x0 <= self.body.x < s.x1 and s.y < self.body.y:
                return s
        return None

    def _do_watch(self):
        yield from self._face("right")
        yield Play("sit_down")
        while True:
            watch = Watch()
            yield watch
            if watch.reason != "paw":
                break
            yield Play(f"paw_{watch.direction}")
        yield Play("sit_up")

    def _prey(self):
        """Abscisse d'un curseur posé sur la surface du chat, à bonne distance, sinon None."""
        cursor = self.snap.cursor
        seg = self.body.support
        if cursor is None or seg is None or self.clock < self._next_hunt or self.cursor_idle >= PREY_FRESH:
            return None
        cx, cy = cursor
        if not (seg.y - HUNT_LEVEL <= cy <= seg.y + 10) or not seg.spans(cx):
            return None
        return cx if HUNT_MIN <= abs(cx - self.body.x) <= HUNT_MAX else None

    def _do_hunt(self, cx):
        direction = "right" if cx > self.body.x else "left"
        sign = 1 if direction == "right" else -1
        yield from self._face(direction)
        yield WalkTo(cx - sign * HUNT_APPROACH * self.k, idle=False)
        yield Play(f"stalk_{direction}")
        yield Play("pounce", mirrored=direction == "left")
        self._next_hunt = self.clock + HUNT_COOLDOWN

    def _jump_targets(self):
        body = self.body
        out = []
        for s in self.segments:
            if s == body.support or not (body.y - JUMP_UP <= s.y <= body.y + JUMP_DOWN) or s.y == body.y:
                continue
            lo, hi = s.x0 + EDGE_MARGIN * self.k, s.x1 - EDGE_MARGIN * self.k
            if lo >= hi:
                continue
            nearest = min(max(body.x, lo), hi)
            if abs(nearest - body.x) <= JUMP_REACH:
                out.append((s, lo, hi))
        return out

    def _do_jump(self, targets):
        seg, lo, hi = self.rng.choice(targets)
        x = min(max(self.body.x + self.rng.uniform(-JUMP_REACH, JUMP_REACH) / 2, lo), hi)
        yield from self._face("right" if x >= self.body.x else "left")
        yield Jump(x, seg.y)
