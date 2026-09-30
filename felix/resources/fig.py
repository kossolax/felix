"""Format d'image « FIG2 » des ScreenMates Felix II (AdTools, ~2000).

    "FIG2" u16=0 u16=1 u16 w u16 h u16=0 u32 len  zlib(palette 256 × BGRx)
    u16 w u16 h 00×4 FF×6 00×4 u32 len            zlib(w×h octets indexés)

Les lignes sont stockées de bas en haut. L'index 253 (magenta #FF00FF) est
la couleur transparente.
"""
import struct
import zlib
from dataclasses import dataclass

from felix.resources.pe import read_resources

TRANSPARENT_INDEX = 253


@dataclass(frozen=True)
class Image:
    width: int
    height: int
    rgba: bytes


def decode_fig2(data):
    if data[:4] != b"FIG2":
        raise ValueError("pas une image FIG2")
    w, h = struct.unpack_from("<HH", data, 8)
    pal_len = struct.unpack_from("<I", data, 14)[0]
    palette = zlib.decompress(data[18:18 + pal_len])
    pos = 18 + pal_len
    px_len = struct.unpack_from("<I", data, pos + 18)[0]
    pixels = zlib.decompress(data[pos + 22:pos + 22 + px_len])
    if len(pixels) != w * h:
        raise ValueError(f"{len(pixels)} pixels pour {w}×{h}")

    lut = []
    for i in range(256):
        b, g, r = palette[4 * i:4 * i + 3]
        lut.append(bytes((0, 0, 0, 0)) if i == TRANSPARENT_INDEX else bytes((r, g, b, 255)))
    # Lignes stockées de bas en haut, comme un DIB Windows
    rows = [pixels[y * w:(y + 1) * w] for y in range(h - 1, -1, -1)]
    return Image(w, h, b"".join(lut[p] for row in rows for p in row))


def unpack_launcher(data):
    """felix2.exe est un lanceur : EXE/100 = u32 taille + zlib(vrai programme)."""
    blob = read_resources(data)[("EXE", 100)]
    size = struct.unpack_from("<I", blob)[0]
    inner = zlib.decompress(blob[4:])
    if len(inner) != size:
        raise ValueError("taille de l'exécutable interne incohérente")
    return inner
