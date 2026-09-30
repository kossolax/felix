"""Cerveau du chat : scripts d'actions, physique et interactions avec la souris.

Un script est un générateur qui produit des actions (Play, WalkTo, Jump…).
Chaque action tourne jusqu'à sa fin, puis le script reprend. La chute et la
prise à la souris interrompent le script en cours.
"""
import math
import random
from dataclasses import dataclass

from felix.core.anim import Frame, Player
from felix.core.physics import GRAVITY, Body, step
from felix.core.surfaces import compute_surfaces

EDGE_MARGIN = 30
JUMP_UP = 650
JUMP_DOWN = 700
JUMP_REACH = 500
JUMP_APEX = 70
SCARED_FALL = 400


@dataclass
class View:
    animation: str
    frame: Frame
    x: float
    y: float
    mirrored: bool = False
    hidden: bool = False


# --- Actions -----------------------------------------------------------------

class Play:
    """Joue une animation : une fois, ou pendant `duration` secondes si elle boucle."""
    airborne = False

    def __init__(self, name, duration=None):
        self.name = name
        self.duration = duration

    def start(self, pet):
        pet.play(self.name)
        self.elapsed = 0.0
        self.frames = 0

    def update(self, pet, dt):
        self.frames += pet.player.update(dt)
        self.elapsed += dt
        anim = pet.player.animation
        if self.duration is not None:
            return self.elapsed >= self.duration
        if anim.loop:
            return self.frames >= len(anim.frames)
        if pet.player.finished:
            pet.shift(anim.shift)
            return True
        return False


class Hold(Play):
    """Reste figé sur une image d'une animation."""

    def __init__(self, name, index, duration):
        super().__init__(name, duration)
        self.index = index

    def start(self, pet):
        super().start(pet)
        pet.player.index = self.index

    def update(self, pet, dt):
        self.elapsed += dt
        return self.elapsed >= self.duration


class WalkTo:
    airborne = False

    def __init__(self, x):
        self.target = x

    def start(self, pet):
        self.direction = "right" if self.target > pet.body.x else "left"
        pet.play(f"walk_{self.direction}")

    def update(self, pet, dt):
        steps = pet.player.update(dt)
        if not steps:
            return False
        dx = pet.player.animation.dx * steps
        x = pet.body.x + dx
        seg = pet.body.support
        lo, hi = seg.x0 + EDGE_MARGIN, seg.x1 - EDGE_MARGIN
        reached = (x >= self.target) if dx > 0 else (x <= self.target)
        if reached:
            x = self.target
        pet.body.x = min(max(x, lo), hi)
        return reached or pet.body.x in (lo, hi)


class Jump:
    def __init__(self, x, y):
        self.target = (x, y)
        self.airborne = False

    def start(self, pet):
        self.direction = "right" if self.target[0] >= pet.body.x else "left"
        pet.facing = self.direction
        pet.play(f"jump_prep_{self.direction}")
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


# --- Le chat -------------------------------------------------------------------

BEHAVIORS = {
    "walk": 30, "stand": 20, "sit": 14, "sit_back": 5, "wash": 8, "stretch": 5, "jump": 18, "doze": 3,
}


class Pet:
    def __init__(self, animations, rng=None):
        self.anims = animations
        self.rng = rng or random.Random()
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

    # -- animation --
    def play(self, name):
        self.player = Player(self.anims[name])
        facing = self.anims[name].facing
        if facing in ("left", "right"):
            self.facing = facing

    def shift(self, delta):
        if delta == (0, 0) or self.body.support is None:
            return
        seg = self.body.support
        self.body.x = min(max(self.body.x + delta[0], seg.x0 + EDGE_MARGIN), seg.x1 - EDGE_MARGIN)

    # -- interactions --
    @property
    def still(self):
        return self._still

    @still.setter
    def still(self, value):
        self._still = value
        if self.mode == "script" and not getattr(self.action, "airborne", False):
            self._run(self._brain())

    def grab(self, px, py):
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
    def update(self, dt, snap):
        self.snap = snap
        self.segments = compute_surfaces(snap)
        if self.body is None:
            self._spawn()
        hidden = bool(snap.windows) and snap.windows[0].fullscreen
        if not hidden:
            self._update(dt)
        return View(self.player.animation.name, self.player.frame, self.body.x, self.body.y,
                    self.mirrored, hidden)

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
            if self._still:
                yield Play(f"stand_{self.facing}", duration=1.0)
                continue
            choices = dict(BEHAVIORS)
            targets = self._jump_targets()
            if not targets:
                choices.pop("jump")
            name = self.rng.choices(list(choices), weights=list(choices.values()))[0]
            if name == "jump":
                yield from self._do_jump(targets)
            else:
                yield from getattr(self, f"_do_{name}")()

    def _face(self, direction):
        if self.facing != direction:
            yield Play(f"turn_to_{direction}")

    def _do_walk(self):
        seg = self.body.support
        target = self.rng.uniform(seg.x0 + EDGE_MARGIN, seg.x1 - EDGE_MARGIN)
        if abs(target - self.body.x) < 20:
            return
        yield from self._face("right" if target > self.body.x else "left")
        yield WalkTo(target)

    def _do_stand(self):
        yield Play(f"stand_{self.facing}", duration=self.rng.uniform(2, 6))

    def _do_sit(self):
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("sit_front", duration=self.rng.uniform(4, 12))
        yield Play("sit_up")

    def _do_sit_back(self):
        yield from self._face("right")
        yield Play("sit_back_down")
        yield Play("sit_back", duration=self.rng.uniform(4, 10))
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

    def _jump_targets(self):
        body = self.body
        out = []
        for s in self.segments:
            if s == body.support or not (body.y - JUMP_UP <= s.y <= body.y + JUMP_DOWN) or s.y == body.y:
                continue
            lo, hi = s.x0 + EDGE_MARGIN, s.x1 - EDGE_MARGIN
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
