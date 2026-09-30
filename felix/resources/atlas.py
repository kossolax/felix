"""Découpage des planches de sprites en grilles régulières."""

MAX_CROSSING = 0.01  # part maximale de pixels opaques tolérée sur une ligne de coupe


def _crossing_ratio(alpha, w, h, cols, rows):
    cw, ch = w // cols, h // rows
    opaque = total = 0
    for k in range(1, cols):
        for x in (k * cw - 1, k * cw):
            opaque += sum(1 for y in range(h) if alpha[y * w + x])
            total += h
    for k in range(1, rows):
        for y in (k * ch - 1, k * ch):
            opaque += sum(1 for a in alpha[y * w:(y + 1) * w] if a)
            total += w
    return opaque / total if total else 0.0


def guess_grid(alpha, w, h, max_div=12):
    """Devine (colonnes, lignes) : la grille la plus fine dont les coupes ne traversent pas d'image."""
    best = (1, 1)
    for cols in range(1, max_div + 1):
        if w % cols:
            continue
        for rows in range(1, max_div + 1):
            if h % rows or cols * rows <= best[0] * best[1]:
                continue
            if _crossing_ratio(alpha, w, h, cols, rows) <= MAX_CROSSING:
                best = (cols, rows)
    return best


def _shift(row, dx):
    return row << dx if dx >= 0 else row >> -dx


def best_offset(a, b, max_dx, max_dy):
    """Décalage (dx, dy) qui superpose au mieux le masque a sur le masque b.

    a, b : une ligne par entier (bit x = pixel opaque en colonne x). Critère :
    intersection sur union ; à égalité, le plus petit déplacement.
    """
    count_a = sum(r.bit_count() for r in a)
    count_b = sum(r.bit_count() for r in b)
    best, best_key = (0, 0), None
    for dy in range(-max_dy, max_dy + 1):
        for dx in range(-max_dx, max_dx + 1):
            overlap = 0
            for y, row in enumerate(a):
                if 0 <= y + dy < len(b):
                    overlap += (_shift(row, dx) & b[y + dy]).bit_count()
            score = overlap / (count_a + count_b - overlap or 1)
            key = (score, -(abs(dx) + abs(dy)))
            if best_key is None or key > best_key:
                best, best_key = (dx, dy), key
    return best
