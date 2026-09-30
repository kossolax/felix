"""Extension Fun and Games (2001) : le ballon de plage, la souris mécanique, la grenouille.

Les planches ne dessinent le chat que tourné vers la droite (le jouet à sa droite) ; de l'autre
côté, elles sont jouées en miroir.
"""
from felix.core.actions import Bat, Play
from felix.core.ball import BEACH
from felix.core.tuning import BEACH_REST, BEACH_ROUNDS, BEACH_SPEED


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
