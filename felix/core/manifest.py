"""Chargement du manifeste des sprites (sprites/felix.json).

Le manifeste ne contient que des coordonnées : la planche (grille colonnes×lignes)
et, pour chaque animation, les cellules à jouer. Les ancrages (pieds) sont
calculés à partir des boîtes englobantes opaques fournies par `bbox_of`.
"""
from felix.core.anim import Animation, Frame


def parse_frames(spec):
    if isinstance(spec, list):
        return list(spec)
    out = []
    for part in str(spec).split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def _grids(data, sheet_sizes):
    grids = {}
    for key, (cols, rows) in data.get("sheets", {}).items():
        sid = int(key)
        if sid not in sheet_sizes:
            raise ValueError(f"planche {sid} absente")
        w, h = sheet_sizes[sid]
        if w % cols or h % rows:
            raise ValueError(f"planche {sid} : grille {cols}×{rows} incompatible avec {w}×{h}")
        grids[sid] = (cols, rows, w // cols, h // rows)
    return grids


def _anchors(mode, boxes, cell_size, scale):
    boxes = [b or (0, 0, cell_size[0], cell_size[1]) for b in boxes]
    if mode == "track":
        return [((b[0] + b[2]) // 2, b[3]) for b in boxes]
    if isinstance(mode, list):
        return [(mode[0] * scale, mode[1] * scale)] * len(boxes)
    first = boxes[0]
    anchor = ((first[0] + first[2]) // 2, max(b[3] for b in boxes))
    return [anchor] * len(boxes)


def load_manifest(data, sheet_sizes, bbox_of, scale=1):
    """bbox_of(sheet, rect) -> (x0, y0, x1, y1) opaque relatif à la cellule, ou None.

    `scale` : facteur entier d'agrandissement. sheet_sizes et bbox_of portent déjà sur les
    planches agrandies ; les coordonnées écrites dans le manifeste sont multipliées ici.
    """
    grids = _grids(data, sheet_sizes)
    anims = {}
    for name, spec in data.get("animations", {}).items():
        sid = spec["sheet"]
        if sid not in grids:
            raise ValueError(f"{name} : planche {sid} inconnue")
        cols, rows, cw, ch = grids[sid]
        indices = parse_frames(spec["frames"])
        if any(i < 0 or i >= cols * rows for i in indices):
            raise ValueError(f"{name} : image hors de la grille {cols}×{rows}")
        rects = [((i % cols) * cw, (i // cols) * ch, cw, ch) for i in indices]
        anchors = _anchors(spec.get("anchor", "fixed"), [bbox_of(sid, r) for r in rects], (cw, ch), scale)
        shift = tuple(v * scale for v in spec.get("shift", (0, 0)))
        if "exit" in spec:  # pieds du chat sur la dernière image : la position le rejoint à la fin
            shift = (spec["exit"][0] * scale - anchors[-1][0], 0)
        lx, ly = rects[-1][:2]
        marks = tuple(((lx + m[0] * scale, ly + m[1] * scale, m[2] * scale, m[3] * scale), (m[0] * scale, m[1] * scale))
                      for m in spec.get("marks", []))
        anims[name] = Animation(
            name=name,
            sheet=sid,
            frames=tuple(Frame(sid, r, a) for r, a in zip(rects, anchors)),
            fps=spec.get("fps", 10),
            loop=spec.get("loop", False),
            dx=spec.get("dx", 0) * scale,
            facing=spec.get("facing", "front"),
            shift=shift,
            marks=marks,
        )
    return anims
