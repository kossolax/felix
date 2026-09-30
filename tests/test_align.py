from felix.resources.atlas import best_offset


def mask(rows):
    """Lignes de texte '.#' -> liste d'entiers (bit x = colonne x)."""
    return [sum(1 << x for x, c in enumerate(r) if c == "#") for r in rows]


def test_best_offset_finds_the_shift_between_two_frames():
    a = mask(["........",
              "..###...",
              "..#.#...",
              "..###..."])
    b = mask(["........",
              "........",
              ".....###",
              ".....#.#"])
    # le motif de b est celui de a décalé de +3 en x et +1 en y
    assert best_offset(a, b, max_dx=6, max_dy=2) == (3, 1)


def test_identical_frames_have_no_offset():
    a = mask([".##.", "####"])
    assert best_offset(a, a, max_dx=3, max_dy=1) == (0, 0)
