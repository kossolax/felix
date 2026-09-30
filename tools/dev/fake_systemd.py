#!/usr/bin/python3
"""Faux org.freedesktop.systemd1 (bus de session privé de test) : StartUnit répond « done »."""
import itertools
from gi.repository import Gio, GLib

XML = """<node><interface name="org.freedesktop.systemd1.Manager">
<method name="StartUnit"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="o" direction="out"/></method>
<method name="StopUnit"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="o" direction="out"/></method>
<method name="GetUnit"><arg type="s" direction="in"/><arg type="o" direction="out"/></method>
<method name="Subscribe"/>
<signal name="JobRemoved"><arg type="u"/><arg type="o"/><arg type="s"/><arg type="s"/></signal>
</interface></node>"""
jobs = itertools.count(1)

def on_call(conn, sender, path, iface, method, params, invocation):
    if method in ("StartUnit", "StopUnit"):
        unit = params.unpack()[0]
        n = next(jobs)
        job = f"/org/freedesktop/systemd1/job/{n}"
        invocation.return_value(GLib.Variant("(o)", (job,)))
        GLib.timeout_add(50, lambda: conn.emit_signal(None, "/org/freedesktop/systemd1",
            "org.freedesktop.systemd1.Manager", "JobRemoved", GLib.Variant("(uoss)", (n, job, unit, "done"))) and False)
        print("job", method, unit, flush=True)
    elif method == "GetUnit":
        invocation.return_value(GLib.Variant("(o)", ("/org/freedesktop/systemd1/unit/fake",)))
    else:
        invocation.return_value(None)

def on_bus(conn, name):
    conn.register_object("/org/freedesktop/systemd1", Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], on_call, None, None)

Gio.bus_own_name(Gio.BusType.SESSION, "org.freedesktop.systemd1", Gio.BusNameOwnerFlags.NONE, on_bus, None, None)
GLib.MainLoop().run()
