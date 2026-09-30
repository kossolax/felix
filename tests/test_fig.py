import struct
import zlib

import pytest

from felix.resources.fig import TRANSPARENT_INDEX, decode_fig2, unpack_launcher
from tests.pe_builder import build_pe


def make_palette():
    pal = bytearray(1024)
    pal[4 * 1:4 * 1 + 4] = bytes([0x30, 0x20, 0x10, 0])  # BGRx -> RGB (0x10, 0x20, 0x30)
    pal[4 * TRANSPARENT_INDEX:4 * TRANSPARENT_INDEX + 4] = bytes([0xFF, 0x00, 0xFF, 0])
    return bytes(pal)


def make_fig2(w, h, pixels, palette=None):
    zpal = zlib.compress(palette or make_palette())
    zpx = zlib.compress(bytes(pixels))
    return (b"FIG2" + struct.pack("<HHHHH", 0, 1, w, h, 0) + struct.pack("<I", len(zpal)) + zpal
            + struct.pack("<HH", w, h) + b"\0" * 4 + b"\xff" * 6 + b"\0" * 4
            + struct.pack("<I", len(zpx)) + zpx)


def test_decodes_size_and_rgba_pixels():
    img = decode_fig2(make_fig2(2, 1, [1, TRANSPARENT_INDEX]))
    assert (img.width, img.height) == (2, 1)
    assert img.rgba == bytes([0x10, 0x20, 0x30, 255, 0, 0, 0, 0])


def test_rows_are_stored_bottom_up_like_a_dib():
    img = decode_fig2(make_fig2(1, 2, [1, TRANSPARENT_INDEX]))
    # 1re ligne stockée = ligne du bas : le pixel opaque doit finir en bas
    assert img.rgba[3::4] == bytes([0, 255])


def test_magenta_key_is_fully_transparent():
    img = decode_fig2(make_fig2(1, 2, [TRANSPARENT_INDEX, TRANSPARENT_INDEX]))
    assert img.rgba[3::4] == bytes([0, 0])


def test_rejects_bad_magic():
    with pytest.raises(ValueError):
        decode_fig2(b"FIG1" + b"\0" * 40)


def test_rejects_pixel_count_mismatch():
    with pytest.raises(ValueError):
        decode_fig2(make_fig2(3, 3, [1, 1]))


def test_unpacks_inner_exe_from_launcher_resource():
    inner = b"MZ" + b"inner program" * 50
    blob = struct.pack("<I", len(inner)) + zlib.compress(inner)
    launcher = build_pe({"EXE": {100: blob}})
    assert unpack_launcher(launcher) == inner
