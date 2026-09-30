"""Le chaton de l'extension Kitten (2001) : un second personnage, qui suit Felix.

Seul, il a son propre petit cerveau (le script d'origine) : il suit Felix en marchant, trotte
quand il est loin, se couche près de lui en remuant la queue ou en clignant des yeux, regarde
l'écran, fait demi-tour au bord. Pendant les scènes à deux, ce sont les images de Felix qui le
dessinent : il est alors caché (puppet) et réapparaît au pixel près là où elles le laissent.
"""
import random

from felix.core.anim import Player
from felix.core.physics import step
from felix.core.tuning import EDGE_MARGIN, KITTEN_FOLLOW, KITTEN_NEAR, KITTEN_TROT

LIFT = 2  # px : à côté de Felix assis, ses images dessinent le chaton un peu plus haut
LYING = ("kitten_crouch", "kitten_lie", "kitten_land_crouch")  # poses couchées : il se relève avant de repartir
SITTING = {"kitten_sit", "kitten_sit_tail", "kitten_sit_still", "kitten_sit_from_appear"}


class KPlay:
    """Joue une animation du chaton : une fois (un cycle si elle boucle), ou `duration` s."""

    def __init__(self, name, duration=None, keep_lift=False):
        self.name, self.duration, self.keep_lift = name, duration, keep_lift

    def start(self, kitten):
        if not self.keep_lift:
            kitten.lift = 0  # changement de pose : il retrouve le sol
        kitten.play(self.name)
        kitten.shift(kitten.player.animation.enter[0])
        self.elapsed = 0.0
        self.frames = 0

    def update(self, kitten, dt):
        self.frames += kitten.player.update(dt)
        self.elapsed += dt
        anim = kitten.player.animation
        if self.duration is not None:
            return self.elapsed >= self.duration
        if anim.loop:
            return self.frames >= len(anim.frames)
        if kitten.player.finished:
            kitten.shift(anim.shift[0])
            return True
        return False


class KWalk:
    """Marche (ou trotte, s'il est loin) jusqu'à `target`, sans quitter sa surface."""

    def __init__(self, target):
        self.target = target

    def start(self, kitten):
        kitten.lift = 0
        self.sign = 1 if self.target > kitten.x else -1
        gait = "trot" if abs(self.target - kitten.x) > KITTEN_TROT * kitten.k else "walk"
        kitten.play(f"kitten_{gait}_{'right' if self.sign > 0 else 'left'}")

    def update(self, kitten, dt):
        if kitten.leaving:
            return True  # on l'a caché : il s'arrête pour s'effacer
        steps = kitten.player.update(dt)
        if not steps:
            return False
        x = kitten.x + kitten.player.animation.dx * steps  # dx est déjà à l'échelle
        reached = (x - self.target) * self.sign >= 0
        if reached:
            x = self.target
        lo, hi = kitten.bounds()
        if self.sign > 0:  # bornée devant lui seulement : jamais ramené en arrière d'un coup
            x = min(x, max(hi, kitten.x))
            stop = x >= hi
        else:
            x = max(x, min(lo, kitten.x))
            stop = x <= lo
        kitten.x = x
        return reached or stop


class Kitten:
    def __init__(self, anims, x, y, support=None, rng=None, scale=1):
        self.anims = anims
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.support, self.owner_rect = support, None
        self.k = scale
        self.rng = rng or random.Random()
        self.facing = "right"
        self.lift = 0  # px au-dessus du sol : les images de Felix assis le dessinent 2 px plus haut
        self.visible = True
        self.puppet = False  # dessiné par les images de Felix : son cerveau attend
        self.held = False
        self.falling = False
        self.leaving = False  # on l'a caché : il s'assoit et s'efface
        self.gone = False
        self.goal = None  # (x, direction, pose) où Felix l'attend pour une scène à deux
        self.ready = False
        self.pet = None
        self.player = None
        self.action = None
        self.script = None
        self.play("kitten_stand_right")

    # -- état --
    def play(self, name):
        anim = self.anims[name]
        self.player = Player(anim)
        if anim.facing in ("left", "right"):
            self.facing = anim.facing

    def bounds(self):
        seg = self.support
        if seg is None:
            return self.x, self.x
        m = EDGE_MARGIN * self.k
        return seg.x0 + m, seg.x1 - m

    def shift(self, dx):
        """Les pieds rejoignent le chaton dessiné, sans quitter sa surface."""
        seg = self.support
        self.x = self.x + dx if seg is None else min(max(self.x + dx, seg.x0), seg.x1 - 1)

    def set_animations(self, anims, scale):
        """Changement de taille à chaud."""
        index = self.player.index
        self.anims, self.k = anims, scale
        self.player = Player(anims[self.player.animation.name])
        self.player.index = min(index, len(self.player.animation.frames) - 1)

    def run(self, script):
        self.script = script
        self.action = None

    def spawn(self, x, y, anims, lift=0, support=None):
        """Réapparaît en (x, y), dans les animations `anims` (relais des images de Felix), puis vit."""
        self.x, self.y = float(x), float(y)
        if support is not None:
            self.support = support
        self.owner_rect = None  # la fenêtre a pu bouger pendant la scène : on repart de là où elle est
        self.lift, self.visible, self.puppet = lift, True, False
        self.goal, self.ready = None, False
        self.run(self._then(anims))

    def hide(self):
        """Les images de Felix le dessinent désormais."""
        self.visible, self.puppet = False, True
        self.goal, self.ready = None, False

    def free(self):
        """La scène à deux est abandonnée (Felix attrapé, tombé…) : il reprend sa vie là où il est."""
        self.goal, self.ready = None, False
        if self.puppet:
            self.visible, self.puppet, self.lift = True, False, 0
            self.run(self._then([f"kitten_stand_{self._side()}"]))

    # -- souris --
    def grab(self):
        self.held, self.falling = True, False
        self.goal, self.ready = None, False
        self.support = self.owner_rect = None
        self.vx = self.vy = 0.0
        self.lift = 0
        self.play("kitten_held")

    def move_to(self, x, y):
        self.x, self.y = float(x), float(y)

    def release(self):
        self.held = False
        self.falling = True
        self.play("kitten_fall")

    # -- boucle --
    def update(self, dt, pet, snap, segs):
        self.pet = pet
        if self.gone or self.puppet:
            return
        if self.held:
            self.player.update(dt)
            return
        step(self, dt, snap, segs)
        if self.support is None:
            if not self.falling:
                self.falling = True
                self.play("kitten_fall")
            self.player.update(dt)
            return
        if self.falling:  # atterrissage
            self.falling = False
            self.run(self._then(["kitten_land", "kitten_land_crouch"]))
        if self.script is None:
            self.run(self._brain())
        if self.action is None or self.action.update(self, dt):
            self.action = next(self.script)
            self.action.start(self)

    # -- cerveau --
    def _then(self, anims):
        for name in anims:
            yield KPlay(name, keep_lift=True)
        yield from self._brain()

    def _side(self):
        return self.facing if self.facing in ("left", "right") else "right"

    def _turn(self, direction):
        if self._side() != direction:
            yield KPlay(f"kitten_turn_to_{direction}")

    def _felix(self):
        """Felix, s'il est là et sur la même surface que le chaton."""
        pet = self.pet
        if pet is None or pet.away or pet.body is None or pet.body.support is None:
            return None
        return pet if pet.body.support == self.support else None

    def _brain(self):
        """Le cerveau d'origine (0x649) : debout un moment entre deux actions (2,3 s tourné à
        droite, 1 s à gauche), puis il regarde, cligne des yeux ou se couche, à parts égales."""
        while True:
            if self.leaving:
                yield from self._fade_out()
                return
            if self.player.animation.name.startswith(LYING):
                yield KPlay(f"kitten_getup_{self._side()}")  # couché : il se relève d'abord
                continue
            if self.goal is not None:
                yield from self._to_goal()
                continue
            felix = self._felix()
            if felix is not None and abs(felix.body.x - self.x) > KITTEN_FOLLOW * self.k:
                yield from self._follow(felix)
                continue
            side = self._side()
            yield KPlay(f"kitten_stand_{side}", duration=2.3 if side == "right" else 1.0)
            if self.leaving or self.goal is not None:
                continue
            r = self.rng.random()
            if r < 0.3:
                yield KPlay(f"kitten_look_{side}")
            elif r < 0.6:
                yield KPlay(f"kitten_blink_{side}")
            elif r < 0.9:
                yield from self._lie()
            else:
                yield from self._sit()

    def _follow(self, felix):
        direction = "right" if felix.body.x > self.x else "left"
        yield from self._turn(direction)
        sign = 1 if direction == "right" else -1
        yield KWalk(felix.body.x - sign * KITTEN_NEAR * self.k)

    def _lie(self):
        side = self._side()
        yield KPlay(f"kitten_lie_{side}")
        for _ in range(self.rng.randint(2, 8)):
            felix = self._felix()
            if self.leaving or self.goal is not None or (
                    felix is not None and abs(felix.body.x - self.x) > KITTEN_FOLLOW * self.k):
                break
            yield KPlay(f"kitten_crouch_{'tail' if self.rng.random() < 0.5 else 'blink'}_{side}")
        yield KPlay(f"kitten_getup_{side}")

    def _sit(self):
        yield from self._turn("right")  # ses images assises le montrent tourné à droite
        yield KPlay("kitten_sit")
        for _ in range(self.rng.randint(2, 5)):
            if self.leaving or self.goal is not None:
                break
            yield KPlay("kitten_sit_tail")
        yield KPlay("kitten_sit_up")

    def _to_goal(self):
        """Va où Felix l'attend, dans la pose où ses images vont le reprendre : debout, ou couché
        (lie) au bout d'un battement de queue, 2 px plus haut, à côté de Felix assis."""
        x, direction, pose = self.goal
        if abs(x - self.x) > 1:
            yield from self._turn("right" if x > self.x else "left")
            yield KWalk(x)
        if self.goal is None:
            return
        yield from self._turn(direction)
        if abs(self.goal[0] - self.x) > 1:
            self.goal = None  # pas pu l'atteindre (bord)
            return
        self.x = self.goal[0]
        hold = f"kitten_stand_{direction}"
        if pose == "lie":
            self.lift = LIFT * self.k
            yield KPlay(f"kitten_lie_{direction}", keep_lift=True)
            yield KPlay(f"kitten_crouch_tail_{direction}", keep_lift=True)
            hold = "kitten_crouch_tail_end"
        self.ready = self.goal is not None
        while self.goal is not None and not self.leaving:
            yield KPlay(hold, duration=0.2, keep_lift=True)
        self.goal, self.ready = None, False

    def _fade_out(self):
        """Il s'assoit (s'il ne l'est pas déjà) et s'efface : 728 [4, 13, 14] de l'original."""
        name = self.player.animation.name
        if name.startswith(LYING):
            yield KPlay(f"kitten_getup_{self._side()}")
        if name not in SITTING:
            yield from self._turn("right")
            yield KPlay("kitten_sit")
        yield KPlay("kitten_fade")
        self.gone = True
        while True:
            yield KPlay("kitten_fade", duration=1.0)
