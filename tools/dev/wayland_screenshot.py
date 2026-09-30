#!/usr/bin/python3
"""wayland_screenshot.py OUT.png : capture du GNOME headless via org.gnome.Shell.Screenshot (nom autorisé pris sur le bus privé)."""
import sys
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
              GLib.Variant("(su)", ("org.gnome.Screenshot", 4)), None, 0, -1)
ok, path = bus.call_sync("org.gnome.Shell.Screenshot", "/org/gnome/Shell/Screenshot", "org.gnome.Shell.Screenshot",
                         "Screenshot", GLib.Variant("(bbs)", (False, False, sys.argv[1])), None, 0, 10000).unpack()
print(ok, path)
