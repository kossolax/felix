# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : pyinstaller felix.spec  →  dist/felix/ (onedir, sans console)
# Graphismes d'origine embarqués (assets/original, voir CREDITS.md) : rien à télécharger.
import os
import re
import subprocess
import sys

datas = [("sprites", "sprites"), ("assets/original", "assets/original"), ("assets/sounds", "assets/sounds"),
         ("assets/icon", "assets/icon"), ("CREDITS.md", ".")]

# rien à télécharger (pas d'OpenSSL), ni vidéo ni calcul parallèle côté Qt
excludes = ["tkinter", "ssl", "_ssl", "_hashlib", "PySide6.QtMultimediaWidgets", "PySide6.QtConcurrent"]
if sys.platform == "win32":
    hidden = ["felix.platform.windows"]
    excludes += ["Xlib", "jeepney"]
else:
    hidden = ["felix.platform.x11", "felix.platform.gnome_shell", "jeepney.io.blocking", "Xlib.ext.randr"]

# Le paquet ne garde que ce que le chat charge vraiment : les modules Python et leurs extensions,
# les plugins Qt dont il se sert, et les bibliothèques que tout cela importe (calculées ici, pas
# listées à la main). Partent ainsi le plugin vidéo FFmpeg (QSoundEffect s'en passe) et ce qu'il
# tire (Qt Quick, Qml, OpenGL), le rendu OpenGL logiciel, le thème GTK et GTK lui-même, les formats
# d'image autres que PNG, le clavier virtuel, OpenSSL et les traductions de Qt (jamais chargées).
PLUGINS = re.compile(r"/plugins/(platforms/(lib)?q(windows|xcb|offscreen|minimal)\.|styles/"
                     r"|platformthemes/libqxdgdesktopportal\.)")
ALWAYS = re.compile(r"(?i)^((lib)?python3|api-ms-win-|ucrtbase|vcruntime|msvcp|concrt)")  # Python et CRT
TRANSLATIONS = re.compile(r"(^|/)PySide6/(Qt/)?translations/")


def _name(dest):
    name = os.path.basename(dest.replace("\\", "/"))
    return name.lower() if sys.platform == "win32" else name


def _imports(path):
    """Bibliothèques qu'un binaire importe (table d'import PE, ou DT_NEEDED d'un ELF)."""
    if sys.platform == "win32":
        import pefile
        pe = pefile.PE(path, fast_load=True)
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        return [e.dll.decode() for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])]
    out = subprocess.run(["readelf", "-d", path], capture_output=True, text=True, check=True).stdout
    return re.findall(r"\(NEEDED\).*\[(.+?)\]", out)


def _slim(binaries, datas):
    sources = {}
    roots = []
    for dest, src, kind in binaries:
        name = _name(dest)
        sources.setdefault(name, []).append(src)
        path = "/" + dest.replace("\\", "/")
        if "/plugins/" in path:
            if PLUGINS.search(path):
                roots.append(name)
        elif kind == "EXTENSION" or ALWAYS.match(name):
            roots.append(name)
    keep = set()
    while roots:
        name = roots.pop()
        if name in keep or name not in sources:
            continue
        keep.add(name)
        for src in sources[name]:
            roots.extend(_name(dep) for dep in _imports(src))

    def kept(entry):
        dest, _src, kind = entry
        if kind in ("BINARY", "EXTENSION", "SYMLINK"):
            return _name(dest) in keep or bool(ALWAYS.match(_name(dest)))
        return not TRANSLATIONS.search(dest.replace("\\", "/"))

    return [b for b in binaries if kept(b)], [d for d in datas if kept(d)]


a = Analysis(["run.py"], datas=datas, hiddenimports=hidden, excludes=excludes)
a.binaries, a.datas = _slim(a.binaries, a.datas)
if sys.platform != "win32":
    # Linux : les bibliothèques du système (libstdc++, glib, X11, PulseAudio…) viennent des paquets de
    # la distribution, que le .deb déclare en dépendances (dpkg-shlibdeps) ; Python et Qt restent embarqués.
    a.exclude_system_libraries()
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="felix", console=False, icon="assets/icon/felix.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="felix")
