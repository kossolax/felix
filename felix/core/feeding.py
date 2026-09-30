"""Extension Feeding (2001) : pâtée, lait et friandises Felix, tenus au bout du curseur.

Comme dans l'original, l'appli montre la boîte, la brique ou le sachet sous le curseur ; le chat
attend assis, et remue la queue quand le curseur approche. Un clic gauche sert (serve), un clic
droit reprend l'objet (stop_holding). Chaque clic avec le sachet fait tomber une friandise
(drop_treat) ; le chat va les manger une à une, là où elles sont tombées.
"""
import math

from felix.core.actions import Jump, Play, WalkTo
from felix.core.ball import Ball, BallKind
from felix.core.tuning import (
    CAN_ROOM, CARTON_ROOM, EDGE_MARGIN, HOLD_PATIENCE, JUMP_DOWN, JUMP_REACH, JUMP_UP, TREAT_FALL, TREAT_FOOD,
    TREAT_REACH, WAG_NEAR,
)

TREAT = BallKind("treats_treat", 4, 1000, 10_000.0, 0.0, 0, None, frames=1, grabbable=False)
NEEDS = {"can": "can_serve", "carton": "carton_pour", "treats": "treats_eat_right"}  # animations requises


class AwaitItem:
    """Assis devant l'objet qu'on tient : immobile, ou la queue qui remue quand le curseur est tout
    près ; jusqu'à ce qu'on serve, qu'on le reprenne, ou que la patience s'épuise."""
    airborne = False

    def __init__(self, still, wag):
        self.still, self.wag = still, wag

    def start(self, pet):
        self.elapsed = 0.0
        pet.play(self.still)

    def _near(self, pet):
        cursor = pet.snap.cursor if pet.snap else None
        if cursor is None:
            return False
        hx, hy = pet.head()
        return math.hypot(cursor[0] - hx, cursor[1] - hy) <= WAG_NEAR * pet.k

    def update(self, pet, dt):
        self.elapsed += dt
        if pet._item_state != "held" or self.elapsed >= HOLD_PATIENCE:
            return True
        wrapped = pet.player.update(dt) and pet.player.index == 0
        playing = pet.player.animation.name
        if playing == self.still and self._near(pet):
            pet.play(self.wag)
        elif playing == self.wag and wrapped and not self._near(pet):
            pet.play(self.still)  # la queue finit son tour avant de s'arrêter
        return False


class LookAtCursor:
    """Debout, tourné vers le curseur (le sachet), un instant."""
    airborne = False

    def __init__(self, duration):
        self.duration = duration

    def start(self, pet):
        self.elapsed = 0.0
        pet.play(f"stand_{pet.facing if pet.facing in ('left', 'right') else 'right'}")

    def update(self, pet, dt):
        self.elapsed += dt
        pet.player.update(dt)
        cursor = pet.snap.cursor if pet.snap else None
        if cursor is not None and abs(cursor[0] - pet.body.x) > 20:
            want = "right" if cursor[0] > pet.body.x else "left"
            if want != pet.facing:
                pet.play(f"stand_{want}")
        return self.elapsed >= self.duration


class FeedingScenes:
    """Scènes du chat (mêlées à Pet) ; chacune ne se joue que si l'extension est installée."""

    @property
    def holding(self):
        """Ce que l'utilisateur tient au bout du curseur pour le chat (can, carton, treats), sinon None."""
        return self._item if self._item_state == "held" else None

    def hold_item(self, kind):
        if NEEDS[kind] not in self.anims or self.body is None or self._item_state is not None:
            return
        self._item, self._item_state = kind, "held"
        self.request(kind)

    def serve(self):
        if self._item_state == "held" and self._item in ("can", "carton"):
            self._item_state = "served"

    def stop_holding(self):
        if self._item_state == "held":
            self._item_state = "done"

    def drop_treat(self, x, y):
        """Une friandise tombe du sachet, en (x, y)."""
        if self._item == "treats" and self._item_state == "held":
            treat = Ball(x, y, scale=self.k, kind=TREAT)
            treat.kick(0.0, TREAT_FALL * self.k)
            treat.taken = False
            self.treats.append(treat)

    def _end_item(self):
        self._item = self._item_state = None

    def _do_can(self):
        """Pâtée Felix : il attend la boîte, assis ; servie, la gamelle apparaît, il hume, mange,
        et la gamelle vide s'efface."""
        if self._item != "can":
            return
        try:
            yield from self._make_room(*CAN_ROOM)
            yield from self._face("right")
            yield Play("sit_down")
            yield AwaitItem("can_sit", "can_wag")
            if self._item_state != "served":
                yield Play("sit_up")  # on l'a reprise
                return
            self._item_state = "eating"
            yield Play("can_sit", duration=0.4)
            yield Play("can_serve", event="purr")
            yield Play("can_eat", event="crunch")
            yield Play("can_eat_more", event="crunch")
            for i in range(self.rng.randint(0, 4)):
                yield Play("can_munch", event="crunch" if i % 2 else None)
            yield Play("can_eat_last", event="crunch")
            self.needs.feed()
            yield Play("can_done")
            yield Play("can_rise")
        finally:
            self._end_item()

    def _do_carton(self):
        """Lait Felix : la gamelle vide apparaît, il attend la brique ; servie, elle verse, il lape
        pendant que le lait baisse, se pourlèche, et la gamelle s'efface."""
        if self._item != "carton":
            return
        try:
            yield from self._make_room(*CARTON_ROOM)
            yield from self._face("right")
            yield Play("sit_down")
            yield Play("carton_bowl_in")
            yield AwaitItem("carton_sit", "carton_wag")
            if self._item_state != "served":
                yield Play("carton_bowl_out")
                yield Play("sit_up")
                return
            self._item_state = "eating"
            for name in ("carton_pour", "carton_look", "carton_lean"):
                yield Play(name)
            yield Play("carton_lap", event="lap")
            for _ in range(self.rng.randint(0, 3)):
                yield Play("carton_lap_loop", event="lap")
            yield Play("carton_lap_down", event="lap")
            yield Play("carton_lap_last", event="lap")
            self.needs.drink()
            yield Play("carton_lick", event="purr")
            yield Play("carton_clear")
        finally:
            self._end_item()

    def _do_treats(self):
        """Friandises : il regarde le sachet ; chaque friandise tombée, il va la manger là où elle est."""
        if self._item != "treats":
            return
        try:
            waited = 0.0
            while True:
                treat = self._next_treat()
                if treat is not None:
                    waited = 0.0
                    yield from self._eat_treat(treat)
                    continue
                if self._item_state != "held" and all(t.grounded for t in self.treats):
                    break
                waited += 0.5
                if waited >= HOLD_PATIENCE:
                    self._item_state = "done"
                yield LookAtCursor(0.5)
        finally:
            self.treats = []
            self._end_item()

    def _next_treat(self):
        """La friandise posée la plus proche qu'il peut atteindre ; les autres sont perdues."""
        seg = self.body.support
        for treat in [t for t in self.treats if t.grounded]:
            if treat.support != seg and self._treat_leap(treat) is None:
                self.treats.remove(treat)  # hors d'atteinte
        landed = [t for t in self.treats if t.grounded]
        return min(landed, key=lambda t: abs(t.x - self.body.x)) if landed else None

    def _treat_leap(self, treat):
        s = treat.support
        if not (self.body.y - JUMP_UP <= s.y <= self.body.y + JUMP_DOWN) or abs(treat.x - self.body.x) > JUMP_REACH:
            return None
        m = EDGE_MARGIN * self.k
        sign = 1 if treat.x >= self.body.x else -1
        x = treat.x - sign * TREAT_REACH[0 if sign > 0 else 1] * self.k
        return (x, s.y) if s.x0 + m <= x <= s.x1 - m else None

    def _eat_treat(self, treat):
        sign = 1 if treat.x >= self.body.x else -1
        side = "right" if sign > 0 else "left"
        if treat.support != self.body.support:
            yield from self._face(side)
            yield Jump(*self._treat_leap(treat))
            return
        target = treat.x - sign * TREAT_REACH[0 if sign > 0 else 1] * self.k
        if abs(target - self.body.x) > 1:
            yield from self._face("right" if target > self.body.x else "left")
            yield WalkTo(target, idle=False, margin=4)
        if treat not in self.treats or treat.support != self.body.support or abs(self.body.x - target) > 3:
            if treat in self.treats:
                self.treats.remove(treat)  # au bord, hors d'atteinte
            return
        self.body.x = target
        yield from self._face(side)
        treat.taken = True  # dessinée par les images du chat
        yield Play(f"treats_crouch_{side}")
        self.treats.remove(treat)
        yield Play(f"treats_eat_{side}", event="crunch")
        self.needs.hunger = max(0.0, self.needs.hunger - TREAT_FOOD)
        yield Play(f"treats_rise_{side}", event="purr")
