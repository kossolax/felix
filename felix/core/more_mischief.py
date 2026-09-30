"""Extension More Mischief (2001-2002) : la déchirure dans l'écran, le papillon, le tas de feuilles.

Des bêtises que le chat fait de lui-même (sans menu, comme l'original). Listes d'images, cadences
et points chauds relevés dans la DLL de l'extension ; les planches ne regardent que vers la droite,
jouées en miroir quand la place manque de ce côté.
"""
from felix.core.actions import Hold, Play, WalkTo
from felix.core.tuning import BUTTERFLY_ROOM, EDGE_MARGIN, LEAVES_ROOM, TEAR_ROOM, WALK_ON

MORE_MISCHIEF_EXT = {"tear": 1, "butterfly": 1, "leaves": 1}  # poids faibles : scènes longues
ROOMS = {"tear": TEAR_ROOM, "butterfly": BUTTERFLY_ROOM, "leaves": LEAVES_ROOM}
HIDDEN = frozenset({"tear_inside", "tear_wait",  # le chat est dans la déchirure : rien à attraper
                    "kitten_flap_through", "kitten_flap_push", "kitten_flap_wait"})  # … ou passé la chatière


class MoreMischiefScenes:
    """Scènes du chat (mêlées à Pet) ; chacune ne se joue que si l'extension est installée."""

    def _more_mischief_ext(self):
        """Celles qui tiennent sur la surface du chat : sinon le décor déborderait dans le vide."""
        if "tear_scratch" not in self.anims:
            return {}
        return {name: w for name, w in MORE_MISCHIEF_EXT.items() if self._has_room(*ROOMS[name])}

    def _side(self, room):
        """En miroir (décor à gauche) seulement si la place manque de l'autre côté, comme l'original."""
        seg = self.body.support
        m = EDGE_MARGIN * self.k
        need_right = max(0, self.body.x + room[1] * self.k - (seg.x1 - m))
        need_left = max(0, (seg.x0 + m) - (self.body.x - room[1] * self.k))
        return need_left < need_right

    def _start(self, room):
        mirrored = self._side(room)
        yield from self._make_room(*(room[::-1] if mirrored else room))
        side = "left" if mirrored else "right"
        yield from self._face(side)
        yield Hold(f"stand_{side}", 0, 0.4, idle=False)  # il s'arrête sur la pose qui raccorde avec la 1re image
        return mirrored

    def _cell_origin(self, name, mirrored):
        """Coin haut-gauche à l'écran de la dernière image de `name`, avant son décalage de fin."""
        f = self.anims[name].frames[-1]
        ax = f.rect[2] - f.anchor[0] if mirrored else f.anchor[0]
        return round(self.body.x - ax), round(self.body.y - f.anchor[1])

    def _walk_on(self, mirrored):
        yield WalkTo(self.body.x + (-WALK_ON if mirrored else WALK_ON) * self.k, idle=False)

    def _do_tear(self):
        """Il déchire l'écran, s'y glisse, joue à coucou dedans, ressort et s'en va ; la déchirure
        se referme derrière lui."""
        if "tear_scratch" not in self.anims or not self._has_room(*TEAR_ROOM):
            return
        m = yield from self._start(TEAR_ROOM)
        for name in ("tear_scratch", "tear_enter", "tear_inside"):
            yield Play(name, mirrored=m)
        yield Play("tear_emerge", mirrored=m, event="meow")
        origin = self._cell_origin("tear_walk_off", m)
        yield Play("tear_walk_off", mirrored=m)
        self.emit(("prop_anim", "tear_close", origin, m))
        yield Play("tear_step_on", mirrored=m, slide=(-12 if m else 12) * self.k)
        yield from self._walk_on(m)

    def _do_butterfly(self):
        """Un papillon se pose sur son nez : il le suit, se dresse, le chasse d'un coup de patte,
        bondit, le laisse marcher sur sa tête, jusqu'à ce qu'il s'envole."""
        if "butterfly_arrive" not in self.anims or not self._has_room(*BUTTERFLY_ROOM):
            return
        m = yield from self._start(BUTTERFLY_ROOM)
        for name in ("butterfly_arrive", "butterfly_nose", "butterfly_sit", "butterfly_follow",
                     "butterfly_look_up", "butterfly_swipe", "butterfly_on_face", "butterfly_off_face",
                     "butterfly_hover", "butterfly_swat", "butterfly_getup", "butterfly_leap", "butterfly_land",
                     "butterfly_head", "butterfly_swat_again", "butterfly_leave"):
            yield Play(name, mirrored=m)
        yield from self._walk_on(m)  # puis il repart en marchant (script 0x3ec de l'original)

    def _do_leaves(self):
        """Un tas de feuilles mortes : à l'affût, il plonge dedans, s'y roule, s'ébroue, le traverse
        et s'en va ; le tas s'efface."""
        if "leaves_appear" not in self.anims or not self._has_room(*LEAVES_ROOM):
            return
        m = yield from self._start(LEAVES_ROOM)
        yield Play("leaves_appear", mirrored=m)
        for _ in range(3):  # tours de l'original : 3 à l'affût, 1 sur le dos, 1 couché
            yield Play("leaves_stalk", mirrored=m)
        yield Play("leaves_pounce", mirrored=m)
        yield Play("leaves_dive", mirrored=m, event="crunch")
        yield Play("leaves_roll", mirrored=m)
        yield Play("leaves_back", mirrored=m)
        yield Play("leaves_roll_back", mirrored=m, event="crunch")
        yield Play("leaves_settle", mirrored=m)
        yield Play("leaves_lie", mirrored=m, event="purr")
        yield Play("leaves_getup", mirrored=m)
        for _ in range(2):
            yield Play("leaves_shake", mirrored=m)
        yield Play("leaves_cross", mirrored=m)
        origin = self._cell_origin("leaves_walk_off", m)
        yield Play("leaves_walk_off", mirrored=m)
        self.emit(("prop_anim", "leaves_fade", origin, m))
        yield Play("leaves_step_on", mirrored=m, slide=(-42 if m else 42) * self.k)
        yield from self._walk_on(m)
