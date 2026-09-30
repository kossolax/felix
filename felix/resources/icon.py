"""Reconstruit un fichier .ico à partir des ressources RT_GROUP_ICON (14) / RT_ICON (3) d'un PE."""
import struct

RT_ICON = 3
RT_GROUP_ICON = 14


def build_ico(resources):
    group = next((data for (kind, _), data in sorted(resources.items(), key=str) if kind == RT_GROUP_ICON), None)
    if group is None:
        return None
    _, _, count = struct.unpack_from("<HHH", group)
    entries = [struct.unpack_from("<BBBBHHIH", group, 6 + 14 * i) for i in range(count)]
    images = [resources[(RT_ICON, e[7])] for e in entries]
    out = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    for (w, h, colors, reserved, planes, bits, _, _), img in zip(entries, images):
        out += struct.pack("<BBBBHHII", w, h, colors, reserved, planes, bits, len(img), offset)
        offset += len(img)
    return out + b"".join(images)
