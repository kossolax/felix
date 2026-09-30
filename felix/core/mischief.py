"""Extension Mischief (2002) : griffures sur la vitre, plante en pot, corbeille.

Des bêtises que le chat fait de lui-même : dans l'original, elles suivaient une marche, sans menu.
Listes d'images et points chauds relevés dans la DLL de l'extension.
"""
from felix.core.actions import Play, WalkTo
from felix.core.tuning import BIN_ROOM, PLANT_ROOM, SCRATCH_CYCLES, SCRATCH_ROOM

MISCHIEF_EXT = {"scratch": 2, "plant": 1, "bin": 1}  # poids parmi les bêtises, si l'extension est là
ROOMS = {"scratch": SCRATCH_ROOM["right"], "plant": PLANT_ROOM, "bin": BIN_ROOM}


class MischiefScenes:
    """Scènes du chat (mêlées à Pet) ; chacune ne se joue que si l'extension est installée."""

    def _mischief_ext(self):
        """Celles qui tiennent sur la surface du chat : sinon le pot flotterait dans le vide."""
        if "bin_appear" not in self.anims:
            return {}
        return {name: w for name, w in MISCHIEF_EXT.items() if self._has_room(*ROOMS[name])}

    def _do_scratch(self):
        """Dos tourné, il se dresse contre la vitre et fait ses griffes ; les rayures restent un
        moment à l'écran, et il repart dans le sens où il allait."""
        if "glass_scratch_left" not in self.anims or not self._has_room(*ROOMS["scratch"]):
            return
        side = self.facing if self.facing in ("left", "right") else "right"
        yield from self._make_room(*SCRATCH_ROOM[side])
        yield from self._face(side)
        yield Play(f"glass_scratch_{side}_rise")
        for _ in range(self.rng.randint(*SCRATCH_CYCLES)):
            yield Play(f"glass_scratch_{side}")
        yield Play(f"glass_scratch_{side}_down")
        yield Play(f"glass_scratch_{side}_leave")  # les rayures restent (marks)
        sign = -1 if side == "left" else 1
        yield WalkTo(self.body.x + sign * self.rng.uniform(80, 200) * self.k, idle=False)

    def _do_plant(self):
        """Un pot de fleurs apparaît : il le renifle, le tapote, en fait le tour, le renverse en se
        frottant, piétine la terre, mâchouille la plante, l'arrache et s'y empêtre, puis s'en va en
        laissant le désordre."""
        if "plant_appear" not in self.anims or not self._has_room(*PLANT_ROOM):
            return
        yield from self._make_room(*PLANT_ROOM)
        yield from self._face("right")
        for name in ("plant_appear", "plant_sniff", "plant_paw", "plant_circle", "plant_sit", "plant_knock",
                     "plant_look", "plant_trample", "plant_turn", "plant_chew"):
            yield Play(name)
        yield Play("plant_eat", event="crunch")
        yield Play("plant_pull")
        yield Play("plant_tangled", event="meow")
        yield Play("plant_leave")
        yield Play("plant_leave_end")  # le désordre reste (marks)
        yield WalkTo(self.body.x - self.rng.uniform(80, 200) * self.k, idle=False)

    def _do_bin(self):
        """La corbeille du bureau apparaît : il la guette, bondit dessus, la renverse et fouille
        dans les papiers qui volent, puis tout s'efface."""
        if "bin_appear" not in self.anims or not self._has_room(*BIN_ROOM):
            return
        yield from self._make_room(*BIN_ROOM)
        yield from self._face("right")
        for name in ("bin_appear", "bin_sniff", "bin_crouch", "bin_pounce", "bin_papers", "bin_papers_settle",
                     "bin_rummage", "bin_dig", "bin_dig_more", "bin_end"):
            yield Play(name)
