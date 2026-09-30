"""Encodeur PNG RGBA minimal (sans dépendance)."""
import struct
import zlib


def _chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def encode_png(width, height, rgba):
    stride = width * 4
    raw = b"".join(b"\0" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))
