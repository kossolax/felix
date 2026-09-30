"""Extension Kitten : les scènes de Felix avec le chaton (felix.core.kitten).

Pendant une scène à deux, les images de Felix dessinent le chaton : on le cache, puis il
réapparaît (spawn) là où elles le laissent, au pixel près (relais relevés sur les planches).
"""
from felix.core.actions import Await, BallView, Play, WalkTo
from felix.core.kitten import LIFT, Kitten
from felix.core.tuning import (
    EDGE_MARGIN, KITTEN_CARRY, KITTEN_FLAP_ROOM, KITTEN_MILK_ROOM, KITTEN_RUB_ROOM, KITTEN_TAIL_ROOM, KITTEN_WAIT,
)

KITTEN_DUO = {"kitten_rub": 4, "kitten_tail": 4, "kitten_flap": 1}  # scènes à deux, quand le chaton est là
ROOMS = {"kitten_rub": KITTEN_RUB_ROOM, "kitten_tail": KITTEN_TAIL_ROOM, "kitten_flap": KITTEN_FLAP_ROOM}
DRAWS_KITTEN = ("kitten_appear", "kitten_bowl", "kitten_milk_")  # Felix dessine le chaton avant qu'il existe


class KittenScenes:
    """Scènes du chat (mêlées à Pet) ; elles ne se jouent que si l'extension est installée."""

    @property
    def kitten_coming(self):
        """On a demandé le chaton : il n'est pas encore là, mais il arrive (et on ne l'a pas décommandé)."""
        return self.kitten is None and not self._kitten_unwanted and (
            self.scene == "kitten_show" or "kitten_show" in self._requests)

    def show_kitten(self):
        if "kitten_appear" not in self.anims or self.kitten is not None:
            return
        self._kitten_unwanted = False  # on a pu changer d'avis pendant qu'il arrivait
        if self.scene != "kitten_show" and "kitten_show" not in self._requests:
            self.request("kitten_show")

    def hide_kitten(self):
        if self.kitten is not None:
            self.kitten.leaving = True
        elif "kitten_show" in self._requests:
            self._requests.remove("kitten_show")
        elif self.scene == "kitten_show":
            self._kitten_unwanted = True  # la scène va au bout, puis il s'efface

    def _abandon_kitten(self):
        """Une scène à deux est coupée (Felix attrapé, tombé, parti) : le chaton reprend vie."""
        if self.kitten is not None:
            self.kitten.free()
        elif self.player is not None and self.player.animation.name.startswith(DRAWS_KITTEN) and self.body:
            self._spawn_kitten(43, ["kitten_sit_still", "kitten_sit_up"], lift=LIFT)  # sa fenêtre fermée : il tombe aussi

    def grab_kitten(self):
        if self.kitten is not None and self.kitten.visible:
            self.kitten.grab()

    def drag_kitten(self, x, y):
        if self.kitten is not None and self.kitten.held:
            self.kitten.move_to(x, y)

    def release_kitten(self, _vx=0.0, _vy=0.0):
        if self.kitten is not None and self.kitten.held:
            self.kitten.release()

    def _kitten_duo(self):
        k = self.kitten
        if k is None or not k.visible or k.leaving or k.held or k.falling or k.goal is not None:
            return {}
        if self.body.support is None or k.support != self.body.support:
            return {}
        return {name: w for name, w in KITTEN_DUO.items() if self._has_room(*ROOMS[name])}

    def _update_kitten(self, dt, snap):
        kitten = self.kitten
        if kitten is None:
            return None
        kitten.update(dt, self, snap, self.segments)
        if kitten.gone:
            self.kitten = None
            return None
        visible = kitten.visible and not self._fullscreen_at(snap, kitten.x, kitten.y - 1)
        return BallView(kitten.x, kitten.y - kitten.lift, kitten.player.index, visible,
                        kitten.player.animation.name, True)

    def _spawn_kitten(self, dx, anims, lift=0):
        """Le chaton reprend vie à dx px des pieds de Felix (relais des images de Felix)."""
        x, y = self.body.x + dx * self.k, self.body.y
        if self.kitten is None:
            self.kitten = Kitten(self.anims, x, y, self.body.support, rng=self.rng, scale=self.k)
        self.kitten.spawn(x, y, anims, lift=lift * self.k, support=self.body.support)
        if self._kitten_unwanted:  # caché pendant qu'il arrivait
            self.kitten.leaving, self._kitten_unwanted = True, False

    def _shoo_kitten(self, left, right):
        """Le chaton s'écarte de la place d'une scène (la gamelle…) et attend à côté."""
        k = self.kitten
        if k is None or not k.visible or k.held or k.falling or k.leaving or k.support != self.body.support:
            return
        margin = 40 * self.k
        x0, x1 = self.body.x - left * self.k - margin, self.body.x + right * self.k + margin
        if not x0 < k.x < x1:
            return
        lo, hi = k.bounds()
        for x in sorted((x0, x1), key=lambda x: abs(x - k.x)):
            if lo <= x <= hi:
                k.goal = (x, "right" if x < self.body.x else "left", "stand")
                self._shooed = k
                return

    def _unshoo_kitten(self):
        k, self._shooed = self._shooed, None
        if k is not None and k is self.kitten and not k.puppet:
            k.goal, k.ready = None, False

    def _do_kitten_show(self):
        """Felix s'assoit et le chaton apparaît à côté de lui ; une fois sur deux, ils boivent du lait."""
        if "kitten_appear" not in self.anims or self.kitten is not None:
            return
        try:
            yield from self._show_kitten_scene()
        finally:
            self._kitten_unwanted = False  # coupée avant qu'il arrive : on repart de zéro

    def _show_kitten_scene(self):
        yield from self._make_room(*KITTEN_MILK_ROOM)
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("sit_front", duration=0.5)
        yield Play("kitten_appear", event="meow")
        if self.rng.random() < 0.5:
            self._spawn_kitten(43, ["kitten_sit_from_appear", "kitten_sit_tail", "kitten_sit_up"], lift=LIFT)
            yield Play("sit_front", duration=self.rng.uniform(2, 5), idle=True)
            yield Play("sit_up")
            return
        yield Play("kitten_bowl")
        yield Play("kitten_bowl_wait", duration=self.rng.uniform(1, 3))
        yield Play("kitten_milk_bottle")
        yield Play("kitten_milk_pour")
        yield Play("kitten_milk_kitten", event="lap")
        yield Play("kitten_milk_lean")
        yield Play("kitten_milk_both", event="lap")
        self.needs.drink()
        yield Play("kitten_milk_done")
        self._spawn_kitten(43, ["kitten_sit_still", "kitten_sit_up"], lift=LIFT)
        yield Play("sit_front", duration=self.rng.uniform(1, 3), idle=True)
        yield Play("sit_up")

    def _call_kitten(self, room, dx):
        """Fait la place, se tourne à droite et attend que le chaton vienne à dx px de ses pieds.
        Renvoie True s'il y est (il est alors caché : les images de Felix le dessinent)."""
        kitten = self.kitten
        if kitten is None or "kitten_rub_approach" not in self.anims:
            return False
        yield from self._make_room(*room)
        yield from self._face("right")
        kitten.goal = (self.body.x + dx * self.k, "right", "stand")
        yield Await("stand_right", lambda: kitten.ready or self.kitten is not kitten or kitten.goal is None,
                    KITTEN_WAIT)
        if self.kitten is not kitten or not kitten.ready:
            if self.kitten is kitten:
                kitten.goal = None
            return False
        kitten.hide()
        return True

    def _do_kitten_rub(self):
        """Le chaton se frotte contre Felix, qui le renifle, le prend par la peau du cou et le porte
        un peu plus loin avant de le reposer."""
        if not (yield from self._call_kitten(KITTEN_RUB_ROOM, -76)):
            return
        yield Play("kitten_rub_approach")
        yield Play("kitten_rub_along", event="purr")
        yield Play("kitten_rub_nuzzle", event="purr")
        yield Play("kitten_pickup")
        seg = self.body.support
        far = min(self.body.x + KITTEN_CARRY * self.k, seg.x1 - (EDGE_MARGIN + 60) * self.k)
        if far > self.body.x + 10:
            yield WalkTo(far, idle=False, gait="kitten_carry")
        yield Play("kitten_put_down_right", event="purr")
        self._spawn_kitten(38, ["kitten_crouch_right"] + ["kitten_crouch_tail_right"] * 4)  # état 9 d'origine
        yield Play("stand_right", duration=self.rng.uniform(1, 3))

    def _do_kitten_tail(self):
        """Felix s'assoit de dos, le chaton guette sa queue qui bat et bondit dessus ; Felix repart."""
        if not (yield from self._call_kitten(KITTEN_TAIL_ROOM, -73)):
            return
        yield Play("kitten_tail_sit")
        yield Play("kitten_tail_stalk")
        before = self.body.x
        yield Play("kitten_tail_play")
        self._spawn_kitten((before - self.body.x) / self.k - 4, ["kitten_after_tail", "kitten_sit_up"])
        yield WalkTo(self.body.x + self.rng.uniform(80, 200) * self.k, idle=False)

    def _do_kitten_flap(self):
        """Une chatière apparaît : Felix la passe, le chaton n'y arrive pas et l'attend ; Felix revient
        et la chatière s'efface."""
        kitten = self.kitten
        if kitten is None or "kitten_flap_appear" not in self.anims:
            return
        yield from self._make_room(*KITTEN_FLAP_ROOM)
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("sit_front", duration=0.5)
        kitten.goal = (self.body.x + 34 * self.k, "right", "lie")
        yield Await("sit_front", lambda: kitten.ready or self.kitten is not kitten or kitten.goal is None, KITTEN_WAIT)
        if self.kitten is not kitten or not kitten.ready:
            if self.kitten is kitten:
                kitten.goal = None
            yield Play("sit_up")
            return
        kitten.hide()
        for name in ("kitten_flap_appear", "kitten_flap_felix_in", "kitten_flap_through", "kitten_flap_push",
                     "kitten_flap_wait", "kitten_flap_back"):
            yield Play(name)
        yield Play("kitten_flap_sit")
        yield Play("kitten_flap_leave")
        self._spawn_kitten(41, ["kitten_stand_right"], lift=LIFT)
        yield Play("sit_front", duration=0.5)
        yield Play("sit_up")
        yield WalkTo(self.body.x + 80 * self.k, idle=False)
