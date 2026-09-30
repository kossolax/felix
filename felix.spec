# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : pyinstaller felix.spec  →  dist/felix/felix.exe (onedir, sans console)
# Les sprites (assets/original) doivent avoir été extraits avant : python tools/extract_felix.py
import sys

datas = [("sprites/felix.json", "sprites"), ("assets/original", "assets/original")]
if __import__("os").path.isdir("assets/sounds"):
    datas.append(("assets/sounds", "assets/sounds"))

a = Analysis(
    ["run.py"],
    datas=datas,
    hiddenimports=["felix.platform.windows"] if sys.platform == "win32" else ["felix.platform.x11"],
    excludes=["tkinter", "Xlib"] if sys.platform == "win32" else ["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="felix",
    console=False,
    icon="assets/original/felix.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="felix")
