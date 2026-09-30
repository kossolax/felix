"""Extension Fun and Games (2001) : le ballon de plage, la souris mécanique, la grenouille.

Les planches ne dessinent le chat que tourné vers la droite (le jouet à sa droite) ; de l'autre
côté, elles sont jouées en miroir.
"""
import math

from felix.core.actions import Bat, Jump, Play, WalkTo, WatchBall
from felix.core.ball import BEACH, MOUSE, Ball
from felix.core.frog import Frog
from felix.core.tuning import (
    BEACH_REST, BEACH_ROUNDS, BEACH_SPEED, EDGE_MARGIN, FROG_APPROACH_PAUSE, FROG_FLEE, FROG_HOP, FROG_NEAR,
    FROG_ROOM,
    FROG_ROUNDS, FROG_WAIT, FROG_WALK, MOUSE_NEAR, MOUSE_PLAY, MOUSE_SPEED, MOUSE_WAIT, MOUSE_WALK,
)


class FunScenes:
    """Scènes du chat (mêlées à Pet) ; chacune ne se joue que si l'extension est installée."""

    def _do_beachball(self):
        """Le ballon arrive en roulant ; le chat va s'asseoir à côté, le tapote et le ballon repart,
        plusieurs fois ; au dernier tour il bondit dessus, le crève et se couche sur le ballon
        dégonflé, qui s'efface (images d'origine)."""
        if "beach_pat" not in self.anims:
            return
        if self.ball is None or self.ball.kind is not BEACH:
            self.ball = None  # une pelote qui traînait laisse la place
            yield from self._toss_in(BEACH)
        rounds = self.rng.randint(*BEACH_ROUNDS)
        for i in range(rounds):
            side = yield from self._reach_ball()
            if side is None:
                return  # parti, hors d'atteinte, ou on ne le lui rend pas
            yield from self._pat_beach_ball(side, last=i == rounds - 1)

    def _pat_beach_ball(self, side, last):
        ball = self.ball
        mirrored = side < 0
        yield from self._face("left" if mirrored else "right")
        ball.vx = 0.0
        yield Play("sit_down", mirrored=mirrored, slide=ball.x - side * BEACH.at_feet * self.k - self.body.x)
        spot = self.body.x + side * BEACH.at_feet * self.k
        if self.ball is not ball or not ball.resting or abs(ball.x - spot) > 1:
            yield Play("sit_up", mirrored=mirrored)  # on le lui a pris
            return
        ball.x = spot
        if last:
            self.ball = None  # les images le dessinent jusqu'au bout : il va le crever
            yield Play("beach_pounce", mirrored=mirrored)
            for _ in range(self.rng.randint(2, 4)):
                yield Play("beach_flat", mirrored=mirrored)
            yield Play("beach_flat_look", mirrored=mirrored)
            yield Play("beach_flat_fade", mirrored=mirrored)
            yield Play("beach_getup", mirrored=mirrored)
            yield Play("sit_up", mirrored=mirrored)
            return
        if self.rng.random() < 0.7:
            yield Play("beach_sit", duration=self.rng.uniform(*BEACH_REST), mirrored=mirrored)
        yield Bat(side, self.rng.uniform(*BEACH_SPEED) * self.k, 0, name="beach_pat")
        yield Play("sit_up", mirrored=mirrored)

    def _meet_toy(self, walk):
        """Un jouet qui se déplace seul va arriver du bout le plus proche de la surface du chat : il
        va à sa rencontre (ou se pousse pour lui laisser la place), et se tourne vers ce bout.
        Renvoie (côté : 1 à droite, bout)."""
        seg = self.body.support
        side = 1 if seg.x1 - self.body.x <= self.body.x - seg.x0 else -1
        end = seg.x1 if side > 0 else seg.x0
        m = EDGE_MARGIN * self.k
        spot = min(max(end - side * self.rng.uniform(*walk) * self.k, seg.x0 + m), seg.x1 - m)
        if abs(spot - self.body.x) > 20:
            yield from self._face("right" if spot > self.body.x else "left")
            yield WalkTo(spot, idle=False)
        yield from self._face("right" if side > 0 else "left")
        self.ball = None  # une balle qui traînait laisse la place
        return side, end

    def _do_mouse(self):
        """La souris mécanique arrive d'un bout de la surface, clé qui tourne ; le chat la guette,
        bondit, l'attrape, la retourne et joue avec, puis la relâche et la regarde partir."""
        seg = self.body.support if self.body is not None else None
        if "mouse_near" not in self.anims or seg is None:
            return
        k = self.k
        side, end = yield from self._meet_toy(MOUSE_WALK)
        mirrored = side < 0
        seg = self.body.support
        self.ball = Ball(end - side * MOUSE.radius * k, seg.y, scale=k, kind=MOUSE)
        self.ball.support = seg
        self.ball.kick(-side * MOUSE_SPEED * k, 0.0)
        yield Play("mouse_notice", mirrored=mirrored)
        wait = WatchBall(MOUSE_WAIT, until="near", near=(MOUSE_NEAR + 3) * k)
        yield wait
        mouse = self.ball
        if not wait.ok or mouse is None:
            return
        mouse.vx = 0.0  # désormais dessinée par les images du chat
        yield Play("mouse_near", mirrored=mirrored)
        yield Play("mouse_pounce", mirrored=mirrored)
        for _ in range(self.rng.randint(*MOUSE_PLAY)):
            yield Play("mouse_play", mirrored=mirrored)
        yield Play("mouse_upright", mirrored=mirrored)
        yield Bat(side, MOUSE_SPEED * k, 0.0, away=True, name="mouse_release")
        yield WatchBall(MOUSE_WAIT, until="gone")

    def _do_frog(self):
        """La grenouille arrive en sautant ; le chat se met à l'affût et bondit, mais elle lui
        échappe d'un saut, plusieurs fois ; puis elle s'en va et il la regarde partir."""
        seg = self.body.support if self.body is not None else None
        if "frog_hop_left" not in self.anims or seg is None:
            return
        k = self.k
        side, end = yield from self._meet_toy(FROG_WALK)
        seg = self.body.support
        frog = Frog(end - side * 25 * k, seg.y, heading=-side, scale=k, rng=self.rng)
        frog.support = seg
        self.ball = frog
        frog.hop(10 ** 6, pause=FROG_APPROACH_PAUSE)
        wait = WatchBall(FROG_WAIT, until="near", near=FROG_NEAR * k)
        yield wait
        if self.ball is not frog or not wait.ok:
            return
        frog.stop()
        yield WatchBall(2.0, until="rest")
        leaps, tries = self.rng.randint(*FROG_ROUNDS), 0
        while leaps > 0 and tries < 3 * FROG_ROUNDS[1]:
            tries += 1
            if self.ball is not frog or frog.support != self.body.support:
                break
            seg = self.body.support
            sign = 1 if frog.x >= self.body.x else -1
            room = seg.x1 - frog.x if sign > 0 else frog.x - seg.x0
            if room < FROG_ROOM * k:  # coincée au bout : elle repasse par-dessus lui pour filer
                hops = math.ceil((abs(frog.x - self.body.x) + FROG_ROOM * k) / (FROG_HOP[-1] * k))
                frog.hop(hops, heading=-sign, pause=(0.05, 0.15))
                yield WatchBall(6.0, until="rest")
                continue
            direction = "right" if sign > 0 else "left"
            yield from self._face(direction)
            yield Play(f"stalk_{direction}")
            if self.ball is not frog or frog.support != self.body.support:
                break
            m = EDGE_MARGIN * k
            target = min(max(frog.x - sign * 30 * k, seg.x0 + m), seg.x1 - m)
            frog.hop(self.rng.randint(*FROG_FLEE), heading=sign, pause=(0.05, 0.15))  # elle file au bond
            yield Jump(target, seg.y, prep=f"leap_prep_{direction}")
            leaps -= 1
            yield WatchBall(3.0, until="rest")
        if self.ball is frog:
            frog.heading = 1 if frog.x >= self.body.x else -1  # elle s'éloigne de lui
            frog.leave()
            yield WatchBall(FROG_WAIT, until="gone")
