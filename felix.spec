# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : pyinstaller felix.spec  →  dist/felix/ (onedir, sans console)
# Graphismes d'origine embarqués (assets/original, voir CREDITS.md) : rien à télécharger.
import sys

datas = [("sprites", "sprites"), ("assets/original", "assets/original"), ("assets/sounds", "assets/sounds"),
         ("assets/icon", "assets/icon"), ("CREDITS.md", ".")]

if sys.platform == "win32":
    hidden, excludes = ["felix.platform.windows"], ["tkinter", "Xlib", "jeepney"]
else:
    hidden = ["felix.platform.x11", "felix.platform.gnome_shell", "jeepney.io.blocking", "Xlib.ext.randr"]
    excludes = ["tkinter"]

a = Analysis(["run.py"], datas=datas, hiddenimports=hidden, excludes=excludes)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="felix", console=False, icon="assets/icon/felix.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="felix")
