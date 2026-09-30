"""Cerveau du chat : scripts d'actions, physique et interactions avec la souris.

Un script est un générateur qui produit des actions (Play, WalkTo, Jump…).
Chaque action tourne jusqu'à sa fin, puis le script reprend. La chute et la
prise à la souris interrompent le script en cours ; les actions d'attente
s'interrompent quand le curseur s'approche.
"""
import math
import random

from felix.core.anim import Player
from felix.core.feeding import FeedingScenes
from felix.core.fun import FunScenes
from felix.core.kitten_scenes import KITTEN_DUO, KittenScenes
from felix.core.mischief import MISCHIEF_EXT, MischiefScenes
from felix.core.more_mischief import HIDDEN, MORE_MISCHIEF_EXT, MoreMischiefScenes
from felix.core.ball import YARN, Ball
from felix.core.mood import Temperament
from felix.core.needs import Needs
from felix.core.physics import Body, step
from felix.core.surfaces import compute_surfaces, monitor_for, support_at
from felix.core.actions import (
    BallView, View, Play, Hold, WalkTo, Watch, Away, Climb, ClimbTop, Jump, WatchBall, Chase,
    Bat,
)
from felix.core.tuning import (
    EDGE_MARGIN, JUMP_APEX, JUMP_UP, JUMP_DOWN, JUMP_REACH, SCARED_FALL, HEAD_HEIGHT, ATTENTION, HUNT_LEVEL,
    HUNT_APPROACH, HUNT_CHANCE, HUNT_COOLDOWN, BORED_AFTER, PREY_FRESH, CURSOR_JITTER, FEED_ROOM, DRINK_ROOM,
    EAT_CYCLES, LAP_CYCLES, FISH_WATCH, FISH_NOSE, PRINTS_ROOM, FISHBOWL_ROOM, TV_ROOM, YARN_ROOM, TV_TIME,
    CLIMB_LIFT, CLIMB_TOP_DROP, CLIMB_MIN, BAKED_BALL, BALL_LAUNCH, BAT_SPEED, AWAY_SPEED,
    BAT_HOP, BALL_ROUNDS, PAT_ROUNDS, BALL_CATCH, POUNCE_RANGE, POUNCE_CHANCE, BAT_ROOM, LEAP_RUNUP,
    BALL_PATIENCE, REACH_TRIES, FINALE_ROOM, DANGLE_BALL, TOSS_HEIGHT, TOSS_SPEED, TOSS_WATCH, BOX_HOP_X,
    BOX_HOP_Y, BALL_OUT_WEIGHT, AWAY_TIME, EDGE_REACH, EDGE_WEIGHT, EDGE_JUMP_CHANCE, EDGE_MIN_DROP,
    EDGE_LAND, OUTING_ROOM, HUNT_MIN, HUNT_MAX,
)


# --- Le chat -------------------------------------------------------------------

BEHAVIORS = {
    "walk": 30, "stand": 20, "sit": 14, "sit_back": 5, "wash": 8, "stretch": 5, "jump": 18, "doze": 3,
}
BEG_WEIGHT = 30
MISCHIEF = {"prints": 3, "fishbowl": 2, "tv": 1, "yarn": 1, "outing": 1}
CLIMB_WEIGHT = 10
# scènes des extensions qu'il fait de lui-même : on ne les coupe pas (AddToNoInterruptionsList
# de l'original) ; un clic ou le menu attendent leur fin
SOLO_SCENES = frozenset(MISCHIEF_EXT) | frozenset(MORE_MISCHIEF_EXT) | frozenset(KITTEN_DUO)
# images où le chat dessiné s'écarte de ses pieds, ou dessine son accessoire (pot, corbeille,
# souris, chaton…) : on ne l'attrape pas, il finirait loin du curseur et l'accessoire disparaîtrait
UNGRABBABLE = ("glass_scratch_", "plant_", "bin_", "tear_", "butterfly_", "leaves_", "kitten_",
               "mouse_near", "mouse_pounce", "mouse_play", "mouse_upright", "mouse_release",
               "beach_pounce", "beach_flat", "beach_getup")


class Pet(FunScenes, FeedingScenes, KittenScenes, MischiefScenes, MoreMischiefScenes):
    def __init__(self, animations, rng=None, needs=None, scale=1):
        self.anims = animations
        self.k = scale  # taille du chat : les distances liées à son corps suivent
        self.rng = rng or random.Random()
        self.needs = needs if needs is not None else Needs()
        self.temper = Temperament(self.rng)
        self._events = []
        self._requests = []
        self.ball = None  # pelote de laine libre, quand elle est sortie
        self.treats = []  # friandises tombées du sachet (extension Feeding)
        self.kitten = None  # le chaton (extension Kitten), quand il est là
        self._item = self._item_state = None  # objet tenu au bout du curseur pour lui (Feeding)
        self._kitten_unwanted = False  # caché pendant qu'il arrivait (Kitten)
        self._shooed = None  # chaton écarté de la gamelle
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
        if self.kitten is not None:
            self.kitten.set_animations(animations, scale)
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
        # les pieds rejoignent le chat dessiné, tant qu'ils restent sur la surface (la marge ne
        # compte pas ici : le ramener en deçà le ferait sauter en arrière)
        self.body.x = min(max(self.body.x + dx, seg.x0), seg.x1 - 1)

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
        if self.ball is not None and self.ball.kind.grabbable:
            self.ball.grab()

    def drag_ball(self, x, y):
        if self.ball is not None and self.ball.held:
            self.ball.move_to(x, y)

    def throw_ball(self, vx, vy):
        """Pelote lâchée à la souris, avec la vitesse du geste : le chat court après."""
        if self.ball is not None and self.ball.held:
            self.ball.throw(vx, vy)
            self._want_to_play()

    def put_ball_away(self):
        self.ball = None

    def _want_to_play(self):
        game = self.ball.kind.scene if self.ball is not None else "yarn"
        if game and not self._still and self.scene != game and game not in self._requests:
            self.request(game)

    def stroke(self):
        """Caresse (clic sans glisser) : le chat s'assoit et ronronne."""
        if self.mode == "script" and self.scene is None and self.grabbable() and self.body.grounded:
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
        if self.scene is None and self.mode == "script" and not getattr(self.action, "airborne", False):
            self._run(self._brain())  # une scène en cours se finit d'abord

    def grabbable(self):
        """Pas dehors, ni caché dans la déchirure, ni dessiné loin de ses pieds, ni en train de manger."""
        name = self.player.animation.name if self.player is not None else ""
        return (not self.away and self.body is not None and name not in HIDDEN
                and not name.startswith(UNGRABBABLE) and self._item_state != "eating")

    def grab(self, px, py):
        if not self.grabbable():
            return
        self._abandon_kitten()
        self.scene = None
        self.mode = "held"
        self._pointer = (px, py)
        self._grab_offset = (self.body.x - px, self.body.y - py)
        self.body.support = None
        self.body.vx = self.body.vy = 0.0
        self.action = None
        self.play(f"held_{self.facing}")

    def drag(self, px, py):
        if self.mode != "held":
            return
        self._pointer = (px, py)
        self.body.x, self.body.y = px + self._grab_offset[0], py + self._grab_offset[1]

    def release(self):
        if self.mode == "held":
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
        treats = self._update_treats(dt, snap)
        kitten = self._update_kitten(dt, snap)
        events, self._events = tuple(self._events), []
        return View(self.player.animation.name, self.player.frame, self.body.x, self.body.y,
                    self.mirrored, hidden, events, ball, treats, kitten)

    def _update_treats(self, dt, snap):
        views = []
        for treat in self.treats:
            treat.update(dt, snap, self.segments)
            visible = not treat.taken and not self._fullscreen_at(snap, treat.x, treat.y - 1)
            views.append(BallView(treat.x, treat.y, 0, visible, treat.kind.anim, False))
        return tuple(views)

    def _update_ball(self, dt, snap):
        ball = self.ball
        if ball is None:
            return None
        ball.update(dt, snap, self.segments)
        if ball.gone:
            self.ball = None
            return None
        name = self.player.animation.name
        drawn = name in BAKED_BALL or (name in BALL_LAUNCH and self.player.index < BALL_LAUNCH[name][0])
        visible = not drawn and not self._fullscreen_at(snap, ball.x, ball.y - 1)
        return BallView(ball.x, ball.y, ball.frame, visible, ball.anim, ball.kind.grabbable)

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
        self._abandon_kitten()
        self.script = script
        self.action = next(self.script)
        self.action.start(self)

    def _start_fall(self):
        self._abandon_kitten()
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
            self._send_off_stray_toy()
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
            choices.update(self._mischief_ext())
            choices.update(self._more_mischief_ext())
            choices.update(self._kitten_duo())
            if self.ball is not None and self.ball.kind is not YARN:
                choices.pop("yarn")  # pas de pelote tant qu'un ballon traîne
            if self._ball_to_play_with() and self.ball.kind.scene:
                choices[self.ball.kind.scene] = BALL_OUT_WEIGHT
            if self.needs.hungry or self.needs.thirsty:
                choices["beg"] = BEG_WEIGHT * (1 + 2 * max(self.needs.hunger, self.needs.thirst))
            targets = self._jump_targets()
            if not targets:
                choices.pop("jump")
            if self._climb_target() is not None:
                choices["climb"] = CLIMB_WEIGHT
            if self._edges():
                choices["edge"] = EDGE_WEIGHT
            name = self.temper.pick(choices)
            if name == "jump":
                yield from self._do_jump(targets)
            elif name in SOLO_SCENES:
                self.scene = name
                yield from getattr(self, f"_do_{name}")()
                self.scene = None
            else:
                yield from getattr(self, f"_do_{name}")()

    def _send_off_stray_toy(self):
        """Un jouet qui se déplace seul (souris, grenouille), resté là après une partie
        interrompue, s'en va tout droit."""
        ball = self.ball
        if ball is not None and ball.kind.scene is None and not ball.exits:
            ball.leave(self.k)

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
        yield Play("stroked", event="purr")  # yeux mi-clos, menton levé
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

    def _has_room(self, left, right):
        """La surface du chat est-elle assez longue pour une scène qui s'étend de `left` px derrière
        ses pieds à `right` px devant (plus la marge des deux bouts) ?"""
        seg = self.body.support if self.body is not None else None
        return seg is not None and seg.x1 - seg.x0 >= (left + right + 2 * EDGE_MARGIN) * self.k

    def _make_room(self, left, right):
        seg = self.body.support
        lo, hi = seg.x0 + left * self.k, seg.x1 - right * self.k
        target = min(max(self.body.x, lo), hi) if lo <= hi else (seg.x0 + seg.x1) / 2
        if abs(target - self.body.x) > 5:
            yield from self._face("right" if target > self.body.x else "left")
            yield WalkTo(target, idle=False)

    def _do_feed(self):
        """Le placard apparaît (trame d'origine), le chat y entre et mange en poussant la porte,
        passe la tête entre les boîtes, ressort, et le placard s'efface."""
        yield from self._make_room(*FEED_ROOM)
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("cupboard_appear")
        yield Play("cupboard_enter")
        for i in range(self.rng.randint(*EAT_CYCLES)):
            yield Play("cupboard_eat", event="crunch" if i % 2 == 0 else None)
        self.needs.feed()
        yield Play("cupboard_peek")
        yield Play("cupboard_exit")
        ghost = self._ghost("cupboard_leave", "cupboard_vanish")
        yield Play("cupboard_leave")
        self.emit(("ghost", *ghost))

    def _ghost(self, name, ghost):
        """Le fantôme tramé `ghost`, à l'écran là où la dernière image de `name` dessine sa couche
        du dessous (le placard) : il reste un instant quand elle disparaît avec le chat."""
        frame = self.anims[name].frames[-1]
        _sheet, _rect, (ox, oy) = frame.under[0]
        g = self.anims[ghost].frames[0]
        x, y = self.body.x - frame.anchor[0] + ox, self.body.y - frame.anchor[1] + oy
        return (g.sheet, *g.rect), (round(x), round(y))

    def _do_drink(self):
        yield from self._make_room(*DRINK_ROOM)
        yield from self._face("right")
        yield Play("milk_arrive")
        yield Play("milk_peek")
        yield Play("milk_around")
        yield Play("milk_spill")
        yield Play("milk_drink")
        for i in range(self.rng.randint(*LAP_CYCLES)):
            yield Play("milk_lap", event="lap" if i % 3 == 0 else None)
        yield Play("milk_done")
        self.needs.drink()

    def _do_prints(self):
        yield from self._make_room(*PRINTS_ROOM)
        yield from self._face("right")
        yield Play("paw_prints")

    def _do_fishbowl(self):
        """Le bocal apparaît ; le chat regarde le poisson nager, y colle le nez, se rassoit pour le
        regarder encore, puis le bocal s'efface. Le poisson nage dans une couche à part (301, 302)."""
        yield from self._make_room(*FISHBOWL_ROOM)
        yield from self._face("right")
        yield Play("sit_down")
        yield Play("fishbowl")
        for _ in range(self.rng.randint(*FISH_WATCH)):
            yield Play("fishbowl_watch")
        yield Play("fishbowl_lean")
        for _ in range(self.rng.randint(*FISH_NOSE)):
            yield Play("fishbowl_nose")
        yield Play("fishbowl_back")
        yield Play("fishbowl_gaze")
        yield Play("fishbowl_leave")
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
        if self.ball is not None and self.ball.kind is not YARN:
            self.ball = None  # le ballon qui traînait laisse la place
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
        yield from self._toss_in(YARN)

    def _toss_in(self, kind):
        """Une balle lancée depuis le bord le plus éloigné de l'écran rebondit vers le chat, qui
        la regarde arriver."""
        mon = monitor_for(self.snap.monitors, self.body.x, self.body.y - 1).geometry
        from_right = mon.right - self.body.x >= self.body.x - mon.x
        r = kind.radius * self.k
        speed = self.rng.uniform(*TOSS_SPEED) * self.k
        self.ball = Ball(mon.right - r if from_right else mon.x + r,
                         max(mon.y + 3 * r, self.body.y - TOSS_HEIGHT * self.k), scale=self.k, kind=kind)
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
                    yield Jump(ball.x - side * ball.kind.at_feet * self.k, seg.y, prep=f"leap_prep_{direction}")
                continue
            yield WalkTo(x, idle=False, gait="trot")
        return None

    def _spot_by_ball(self, seg):
        """Où poser les pieds pour avoir la pelote juste à côté, et de quel côté elle sera. Il la
        renverra de ce côté-là : celui d'où il arrive s'il reste de la place devant elle, sinon il
        fait le tour pour la renvoyer vers le plus grand espace libre."""
        m = EDGE_MARGIN * self.k
        near = 1 if self.ball.x >= self.body.x else -1
        spots = [(self.ball.x - side * self.ball.kind.at_feet * self.k, side) for side in (near, -near)]
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
            x = self.ball.x - side * self.ball.kind.at_feet * self.k
            if s.x0 + m <= x <= s.x1 - m and abs(x - self.body.x) <= JUMP_REACH and self._lands_on(x, s):
                return x, s.y
        return None

    def _lands_on(self, x, s):
        """Un saut vers (x, s.y) y retombe-t-il, sans être arrêté avant par une surface au-dessus
        (sa propre fenêtre, quand la cible est sur le sol en dessous d'elle) ?"""
        top = min(self.body.y, s.y) - JUMP_APEX * self.k
        return not any(t != s and t.spans(x) and top <= t.y < s.y for t in self.segments)

    def _play_at_feet(self, side, last):
        """Assis à côté de la pelote : il la renifle, la tapote puis la renvoie d'un coup de patte ;
        au dernier tour, elle se déroule et s'en va (images d'origine, qui dessinent la pelote)."""
        ball = self.ball
        mirrored = side < 0
        yield from self._face("left" if mirrored else "right")
        ball.vx = 0.0  # rattrapée ; il se recale en s'asseyant pour l'avoir pile où les images la dessinent
        yield Play("sit_down", mirrored=mirrored, slide=ball.x - side * ball.kind.at_feet * self.k - self.body.x)
        spot = self.body.x + side * ball.kind.at_feet * self.k
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

    def _do_edge(self):
        """Va au bout de la fenêtre et regarde en bas (EdgeLeft/EdgeRight de l'original), puis saute
        en bas ou recule."""
        edges = self._edges()
        if not edges:
            return
        side, x = self.rng.choice(edges)
        direction = "right" if side > 0 else "left"
        if abs(x - self.body.x) > 1:
            yield from self._face("right" if x > self.body.x else "left")
            yield WalkTo(x, idle=False, margin=EDGE_REACH)
        yield from self._face(direction)
        yield Play(f"edge_{direction}")
        landing = self._edge_landing(side)
        if landing is not None and self.rng.random() < EDGE_JUMP_CHANCE:
            yield Jump(*landing, prep=f"leap_prep_{direction}")
            return
        yield Play(f"edge_{direction}_back")
        yield from self._face("left" if side > 0 else "right")
        yield WalkTo(self.body.x - side * self.rng.uniform(80, 200) * self.k)

    def _edges(self):
        """Bouts de la fenêtre sous le chat d'où l'on voit dans le vide : [(côté, x des pieds)].
        Pas un bout caché par une fenêtre devant, ni suivi d'une autre surface, ni au bord de l'écran."""
        seg = self.body.support if self.body is not None else None
        if seg is None or seg.owner is None or self.snap is None:
            return []
        rect = next((w.rect for w in self.snap.windows if w.id == seg.owner), None)
        if rect is None:
            return []
        reach = EDGE_REACH * self.k
        out = []
        for side, edge, beyond, real in ((-1, seg.x0, seg.x0 - 1, rect.x == seg.x0),
                                         (1, seg.x1, seg.x1, rect.right == seg.x1)):
            if not real or support_at(self.segments, beyond, seg.y) is not None:
                continue
            if not any(m.geometry.contains(beyond, seg.y - 1) for m in self.snap.monitors):
                continue
            x = edge - side * reach
            if seg.x0 + reach <= x <= seg.x1 - reach:
                out.append((side, x))
        return out

    def _edge_landing(self, side):
        """Où retomber en sautant par-dessus ce bord : la première surface plus bas, à portée."""
        seg = self.body.support
        edge = seg.x1 if side > 0 else seg.x0
        m = EDGE_MARGIN * self.k
        lower = [s for s in self.segments if seg.y + EDGE_MIN_DROP * self.k <= s.y <= seg.y + JUMP_DOWN]
        for s in sorted(lower, key=lambda s: s.y):
            lo, hi = sorted((edge + side * EDGE_LAND[0] * self.k, edge + side * EDGE_LAND[1] * self.k))
            lo, hi = max(lo, s.x0 + m), min(hi, s.x1 - m)
            if lo <= hi:
                return self.rng.uniform(lo, hi), s.y
        return None

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
