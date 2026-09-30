from felix.resources.atlas import guess_grid


def sheet_with_blobs(cols, rows, cw, ch, blob):
    """Grille cols×rows de cellules cw×ch, chaque cellule contient un bloc opaque centré."""
    w, h = cols * cw, rows * ch
    alpha = bytearray(w * h)
    bw, bh = blob
    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cw + (cw - bw) // 2, r * ch + (ch - bh) // 2
            for y in range(y0, y0 + bh):
                alpha[y * w + x0:y * w + x0 + bw] = b"\xff" * bw
    return bytes(alpha), w, h


def test_finds_the_grid_of_separated_frames():
    alpha, w, h = sheet_with_blobs(2, 3, 20, 16, (12, 10))
    assert guess_grid(alpha, w, h) == (2, 3)


def test_does_not_split_frames_that_fill_most_of_the_cell():
    # Cellules 20 px de large avec un bloc de 18 px : couper en 4 colonnes traverserait les blocs
    alpha, w, h = sheet_with_blobs(2, 1, 20, 10, (18, 6))
    assert guess_grid(alpha, w, h) == (2, 1)


def test_single_frame_sheet():
    alpha, w, h = sheet_with_blobs(1, 1, 30, 30, (28, 28))
    assert guess_grid(alpha, w, h) == (1, 1)
