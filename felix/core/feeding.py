"""Extension Feeding (2001) : pâtée, lait et friandises Felix, tenus au bout du curseur.

Comme dans l'original, l'appli montre la boîte, la brique ou le sachet sous le curseur ; le chat
attend assis, et remue la queue quand le curseur approche. Un clic gauche sert (serve), un clic
droit reprend l'objet (stop_holding). Chaque clic avec le sachet fait tomber une friandise
(drop_treat) ; le chat va les manger une à une, là où elles sont tombées.
"""
from felix.core.actions import Jump, Play, WalkTo
from felix.core.ball import Ball, BallKind
from felix.core.tuning import (
    CAN_ROOM, CARTON_ROOM, EDGE_MARGIN, HOLD_PATIENCE, JUMP_DOWN, JUMP_REACH, JUMP_UP, TREAT_FALL, TREAT_FOOD,
    TREAT_REACH, WAG_NEAR,
)

TREAT = BallKind("treats_treat", 4, 1000, 10_000.0, 0.0, 0, None, frames=1, grabbable=False)
NEEDS = {"can": "can_serve", "carton": "carton_pour", "treats": "treats_eat_right"}  # animations requises
SEATED = ("sit_front", "head_", "paw_", "stroked")  # assis de face : il attend l'objet sans se relever


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
        """Le curseur dans sa cellule élargie de WAG_NEAR px (rectangle de l'original)."""
        cursor = pet.snap.cursor if pet.snap else None
        if cursor is None:
            return False
        frame = pet.player.frame
        x0, y0 = pet.body.x - frame.anchor[0], pet.body.y - frame.anchor[1]
        m = WAG_NEAR * pet.k
        return x0 - m <= cursor[0] <= x0 + frame.rect[2] + m and y0 - m <= cursor[1] <= y0 + frame.rect[3] + m

    def update(self, pet, dt):
        self.elapsed += dt
        if pet._item_state == "held" and self.elapsed >= HOLD_PATIENCE:
            pet._item_state = "done"  # il renonce : l'objet quitte le curseur tout de suite
        if pet._item_state != "held":
            return True
        wrapped = pet.player.update(dt) and pet.player.index == 0
        playing = pet.player.animation.name
        if playing == self.still and self._near(pet):
            pet.play(self.wag)
        elif playing == self.wag and wrapped and not self._near(pet):
            pet.play(self.still)  # la queue finit son tour avant de s'arrêter
        return False


class LookAtCursor:
    """Debout, tourné vers le curseur (le sachet), en clignant des yeux ; il se retourne s'il
    passe de l'autre côté. Jusqu'à ce que `done()` soit vrai."""
    airborne = False

    def __init__(self, done):
        self.done = done

    def start(self, pet):
        side = pet.facing if pet.facing in ("left", "right") else "right"
        if pet.player.animation.name != f"treats_wait_{side}":
            pet.play(f"treats_wait_{side}")

    def update(self, pet, dt):
        if self.done():
            return True
        pet.player.update(dt)
        if pet.player.animation.name.startswith("turn_to_"):
            if pet.player.finished:
                pet.play(f"treats_wait_{pet.facing}")
            return False
        cursor = pet.snap.cursor if pet.snap else None
        if cursor is not None and abs(cursor[0] - pet.body.x) > 20:
            want = "right" if cursor[0] > pet.body.x else "left"
            if want != pet.facing:
                pet.play(f"turn_to_{want}")
        return False


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
        self.request(kind)  # s'il est occupé, il viendra ensuite

    def serve(self):
        """Clic avec la boîte ou la brique : servi seulement s'il l'attend déjà, assis devant."""
        if self._item_state == "held" and self._item in ("can", "carton") and isinstance(self.action, AwaitItem):
            self._item_state = "served"
            return True
        return False

    def stop_holding(self):
        if self._item_state != "held":
            return
        if self.scene != self._item and self._item in self._requests:
            self._requests.remove(self._item)  # il n'était pas encore venu : rien à ranger
            self._end_item()
        else:
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

    def _sit_for_item(self):
        """S'assoit face à l'écran pour attendre l'objet, s'il ne l'est pas déjà (il suivait le curseur)."""
        if not self.player.animation.name.startswith(SEATED):
            yield from self._face("right")
            yield Play("sit_down")

    def _do_can(self):
        """Pâtée Felix : il attend la boîte, assis ; servie, la gamelle apparaît, il hume, mange,
        et la gamelle vide s'efface."""
        if self._item != "can":
            return
        try:
            yield from self._make_room(*CAN_ROOM)
            self._shoo_kitten(*CAN_ROOM)
            if self._item_state != "held":
                return  # déjà repris
            yield from self._sit_for_item()
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
            self._unshoo_kitten()

    def _do_carton(self):
        """Lait Felix : la gamelle vide apparaît, il attend la brique ; servie, elle verse, il lape
        pendant que le lait baisse, se pourlèche, et la gamelle s'efface."""
        if self._item != "carton":
            return
        try:
            yield from self._make_room(*CARTON_ROOM)
            self._shoo_kitten(*CARTON_ROOM)
            if self._item_state != "held":
                return  # déjà reprise
            yield from self._sit_for_item()
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
            yield Play("turn_to_right")  # assis de trois quarts : il se tourne avant de repartir
        finally:
            self._end_item()
            self._unshoo_kitten()

    def _do_treats(self):
        """Friandises : il regarde le sachet ; chaque friandise tombée, il va la manger là où elle est.
        Interrompu (attrapé…), il revient finir celles qui restent par terre."""
        if self._item != "treats" and not self.treats:
            return
        try:
            start = self.clock
            while True:
                treat = self._next_treat()
                if treat is not None:
                    start = self.clock
                    yield from self._eat_treat(treat)
                    continue
                if self._item_state != "held" and all(t.grounded for t in self.treats):
                    break
                if self._item_state == "held" and self.clock - start >= HOLD_PATIENCE:
                    self._item_state = "done"  # le sachet s'en va ; il finit ce qui tombe encore
                yield LookAtCursor(lambda: self._item_state != "held" or self._next_treat() is not None
                                   or self.clock - start >= HOLD_PATIENCE)
        finally:
            if self._item == "treats":
                self._end_item()

    def _next_treat(self):
        """La friandise posée la plus proche qu'il peut atteindre ; les autres sont perdues."""
        seg = self.body.support
        if seg is None:
            return None
        for treat in [t for t in self.treats if t.grounded]:
            if treat.support != seg and self._treat_leap(treat, self._closest(seg, treat.x)) is None:
                self.treats.remove(treat)  # hors d'atteinte, même en s'approchant
        landed = [t for t in self.treats if t.grounded]
        return min(landed, key=lambda t: abs(t.x - self.body.x)) if landed else None

    def _closest(self, seg, x):
        m = EDGE_MARGIN * self.k
        return min(max(x, seg.x0 + m), seg.x1 - m)

    def _treat_leap(self, treat, from_x=None):
        """Où sauter pour avoir la friandise, posée sur une autre surface, juste devant lui ; d'abord
        du côté d'où il arrive. None si aucun saut n'y mène depuis `from_x` (sa position)."""
        s = treat.support
        x0 = self.body.x if from_x is None else from_x
        if s is None or not (self.body.y - JUMP_UP <= s.y <= self.body.y + JUMP_DOWN):
            return None
        m = EDGE_MARGIN * self.k
        near = 1 if treat.x >= x0 else -1
        for sign in (near, -near):
            x = treat.x - sign * TREAT_REACH[0 if sign > 0 else 1] * self.k
            if s.x0 + m <= x <= s.x1 - m and abs(x - x0) <= JUMP_REACH and self._lands_on(x, s):
                return x, s.y
        return None

    def _eat_treat(self, treat):
        sign = 1 if treat.x >= self.body.x else -1
        side = "right" if sign > 0 else "left"
        if treat.support != self.body.support:
            if self._treat_leap(treat) is None:  # trop loin : il s'approche d'abord
                spot = self._closest(self.body.support, treat.x)
                if abs(spot - self.body.x) > 1:
                    yield from self._face("right" if spot > self.body.x else "left")
                    yield WalkTo(spot, idle=False)
            leap = self._treat_leap(treat)
            if leap is None or treat not in self.treats:
                return
            yield from self._face("right" if leap[0] >= self.body.x else "left")
            leap = self._treat_leap(treat)  # sa fenêtre a pu bouger ou se fermer pendant le demi-tour
            if leap is not None and treat in self.treats:
                yield Jump(*leap)
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
