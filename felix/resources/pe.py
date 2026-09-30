"""Lecture de la section .rsrc d'un exécutable PE (Windows), en Python pur."""
import struct


def _sections(data):
    if data[:2] != b"MZ" or len(data) < 0x40:
        raise ValueError("pas un exécutable MZ")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("signature PE absente")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + opt_size
    for i in range(count):
        name, vsize, rva, raw_size, raw_ptr = struct.unpack_from("<8sIIII", data, table + 40 * i)
        yield name.rstrip(b"\0"), rva, raw_ptr


def read_resources(data):
    """Renvoie {(type, nom): bytes} ; type/nom sont des int (ID) ou des str.

    Seule la première langue de chaque ressource est gardée.
    """
    rsrc = next(((rva, ptr) for name, rva, ptr in _sections(data) if name == b".rsrc"), None)
    if rsrc is None:
        raise ValueError("section .rsrc absente")
    rva0, base = rsrc

    def key(entry):
        if entry & 0x80000000:
            off = base + (entry & 0x7FFFFFFF)
            n = struct.unpack_from("<H", data, off)[0]
            return data[off + 2:off + 2 + 2 * n].decode("utf-16le")
        return entry

    def entries(dir_off):
        named, ids = struct.unpack_from("<HH", data, dir_off + 12)
        for i in range(named + ids):
            yield struct.unpack_from("<II", data, dir_off + 16 + 8 * i)

    out = {}
    for type_id, type_off in entries(base):
        for name_id, name_off in entries(base + (type_off & 0x7FFFFFFF)):
            _, leaf = next(entries(base + (name_off & 0x7FFFFFFF)))
            data_rva, size = struct.unpack_from("<II", data, base + leaf)
            start = data_rva - rva0 + base
            out[(key(type_id), key(name_id))] = data[start:start + size]
    return out
