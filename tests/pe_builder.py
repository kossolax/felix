"""Construit des PE minimaux avec une section .rsrc, pour les tests."""
import struct

RSRC_RVA = 0x1000


def _name_key(key):
    return (0, key) if isinstance(key, str) else (1, key)


def build_pe(resources, lang=1033):
    """resources: {type: {name: bytes}}, type/name = int ou str."""
    dirs, strings, entries, datas = bytearray(), bytearray(), bytearray(), bytearray()
    # Mise en page : [répertoires][chaînes][entrées de données][données]
    # On calcule d'abord la taille des répertoires.
    types = sorted(resources, key=_name_key)
    n_dirs = 1 + len(types) + sum(len(resources[t]) for t in types)
    n_dir_entries = len(types) + sum(len(resources[t]) for t in types) * 2
    dirs_size = n_dirs * 16 + n_dir_entries * 8
    all_names = [k for k in types if isinstance(k, str)]
    for t in types:
        all_names += [k for k in resources[t] if isinstance(k, str)]
    string_offsets = {}
    for s in all_names:
        if s in string_offsets:
            continue
        string_offsets[s] = dirs_size + len(strings)
        enc = s.encode("utf-16le")
        strings += struct.pack("<H", len(s)) + enc
        if len(strings) % 2:
            strings += b"\0"
    entries_base = dirs_size + len(strings)
    n_leaves = sum(len(resources[t]) for t in types)
    data_base = entries_base + n_leaves * 16

    def dir_header(n_named, n_ids):
        return struct.pack("<IIHHHH", 0, 0, 0, 0, n_named, n_ids)

    def entry_id(key):
        return (0x80000000 | string_offsets[key]) if isinstance(key, str) else key

    # Allocation séquentielle des répertoires
    layout = []  # (offset, contenu à remplir)
    root_off = 0
    next_off = 16 + len(types) * 8
    type_dirs = {}
    for t in types:
        type_dirs[t] = next_off
        next_off += 16 + len(resources[t]) * 8
    lang_dirs = {}
    for t in types:
        for n in sorted(resources[t], key=_name_key):
            lang_dirs[(t, n)] = next_off
            next_off += 16 + 8
    assert next_off == dirs_size

    buf = bytearray(dirs_size)
    named = sum(isinstance(t, str) for t in types)
    buf[0:16] = dir_header(named, len(types) - named)
    for i, t in enumerate(types):
        struct.pack_into("<II", buf, 16 + 8 * i, entry_id(t), 0x80000000 | type_dirs[t])
    leaf = 0
    for t in types:
        names = sorted(resources[t], key=_name_key)
        o = type_dirs[t]
        nnamed = sum(isinstance(n, str) for n in names)
        buf[o:o + 16] = dir_header(nnamed, len(names) - nnamed)
        for i, n in enumerate(names):
            struct.pack_into("<II", buf, o + 16 + 8 * i, entry_id(n), 0x80000000 | lang_dirs[(t, n)])
            lo = lang_dirs[(t, n)]
            buf[lo:lo + 16] = dir_header(0, 1)
            entry_off = entries_base + leaf * 16
            struct.pack_into("<II", buf, lo + 16, lang, entry_off)
            data = resources[t][n]
            entries += struct.pack("<IIII", RSRC_RVA + data_base + len(datas), len(data), 0, 0)
            datas += data
            while len(datas) % 4:
                datas += b"\0"
            leaf += 1
    rsrc = bytes(buf) + bytes(strings) + bytes(entries) + bytes(datas)

    # En-têtes : DOS (0x40) + "PE\0\0" + COFF (20) + 1 section (40)
    pe_off = 0x40
    headers_size = 0x200
    dos = bytearray(pe_off)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, pe_off)
    coff = struct.pack("<HHIIIHH", 0x14C, 1, 0, 0, 0, 0, 0)
    section = struct.pack("<8sIIIIIIHHI", b".rsrc", len(rsrc), RSRC_RVA, len(rsrc), headers_size, 0, 0, 0, 0, 0)
    head = bytes(dos) + b"PE\0\0" + coff + section
    return head + b"\0" * (headers_size - len(head)) + rsrc
