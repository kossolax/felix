# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : pyinstaller felix.spec  →  dist/felix/ (onedir, sans console)
#
# Par défaut, les graphismes d'origine ne sont PAS embarqués : au premier lancement,
# Felix propose de télécharger felix2.exe depuis archive.org et les extrait localement.
# FELIX_BUNDLE_SPRITES=1 les inclut (usage strictement personnel, après tools/extract_felix.py).
import os
import sys

datas = [("sprites", "sprites"), ("assets/sounds", "assets/sounds"), ("assets/icon", "assets/icon")]
if os.environ.get("FELIX_BUNDLE_SPRITES") == "1":
    datas.append(("assets/original", "assets/original"))

if sys.platform == "win32":
    hidden, excludes = ["felix.platform.windows"], ["tkinter", "Xlib", "jeepney"]
else:
    hidden = ["felix.platform.x11", "felix.platform.gnome_shell", "jeepney.io.blocking", "Xlib.ext.randr"]
    excludes = ["tkinter"]

a = Analysis(["run.py"], datas=datas, hiddenimports=hidden, excludes=excludes)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="felix", console=False, icon="assets/icon/felix.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="felix")
