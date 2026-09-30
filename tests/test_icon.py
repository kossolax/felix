import struct

from felix.resources.icon import build_ico

IMG_A = b"A" * 40
IMG_B = b"B" * 24


def grp_icon(entries):
    """GRPICONDIR : en-tête + entrées (w, h, couleurs, 0, plans, bits, taille, id)."""
    out = struct.pack("<HHH", 0, 1, len(entries))
    for w, h, size, rid in entries:
        out += struct.pack("<BBBBHHIH", w, h, 0, 0, 1, 32, size, rid)
    return out


def test_ico_file_references_each_image_by_offset():
    resources = {(14, 100): grp_icon([(32, 32, len(IMG_A), 1), (16, 16, len(IMG_B), 2)]),
                 (3, 1): IMG_A, (3, 2): IMG_B}
    ico = build_ico(resources)
    reserved, kind, count = struct.unpack_from("<HHH", ico)
    assert (reserved, kind, count) == (0, 1, 2)
    w, h, _, _, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", ico, 6)
    assert (w, h, size) == (32, 32, len(IMG_A))
    assert ico[offset:offset + size] == IMG_A
    size2, offset2 = struct.unpack_from("<II", ico, 6 + 16 + 8)
    assert ico[offset2:offset2 + size2] == IMG_B


def test_no_group_icon_gives_none():
    assert build_ico({(3, 1): IMG_A}) is None
