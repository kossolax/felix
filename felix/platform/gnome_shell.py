"""Backend GNOME Shell (Wayland) : interroge l'extension felix-helper sur le bus de session.

Sous Wayland, un client ne voit ni les autres fenêtres ni le curseur hors de ses
surfaces. L'extension (gnome-extension/felix-helper@kossolax.github.io) les
expose sur D-Bus ; l'appli, elle, tourne sous XWayland pour pouvoir se placer
et rester au premier plan. Les coordonnées de l'extension sont celles de la
scène GNOME (logiques) ; CoordMapper les aligne sur les écrans vus par Qt.
"""
import json
import os

from jeepney import DBusAddress, MessageType, new_method_call
from jeepney.io.blocking import open_dbus_connection

from felix.core.world import Rect, WinRect, WorldSnapshot
from felix.platform.base import CoordMapper, NativeState, PollingBackend, qt_logical_monitors

BUS_NAME = "io.github.felix.Helper"
OBJECT_PATH = "/io/github/felix/Helper"
INTERFACE = "io.github.felix.Helper1"
HELPER = DBusAddress(OBJECT_PATH, bus_name=BUS_NAME, interface=INTERFACE)
BUS = DBusAddress("/org/freedesktop/DBus", bus_name="org.freedesktop.DBus", interface="org.freedesktop.DBus")
TIMEOUT = 1.0
STATE_EVERY = 3  # GetState une fois sur 3 (5 Hz), GetPointer à chaque tour (15 Hz)


def parse_state(payload):
    data = json.loads(payload)
    mons = sorted(data.get("monitors", []), key=lambda m: (m["geometry"][0], m["geometry"][1]))
    return NativeState(
        monitors=[Rect(*m["geometry"]) for m in mons],
        workareas=[Rect(*m.get("workarea", m["geometry"])) for m in mons],
        windows=[WinRect(w["id"], Rect(*w["rect"]), bool(w.get("fullscreen"))) for w in data.get("windows", [])],
    )


def helper_available():
    try:
        with open_dbus_connection(bus="SESSION") as conn:
            reply = conn.send_and_get_reply(new_method_call(BUS, "NameHasOwner", "s", (BUS_NAME,)), timeout=TIMEOUT)
            return bool(reply.body[0])
    except Exception:
        return False


class GnomeShellBackend(PollingBackend):
    name = "gnome_shell"

    def __init__(self, interval=1 / 15, logical_monitors=qt_logical_monitors,
                 connect=lambda: open_dbus_connection(bus="SESSION"), stale_after=1.0):
        super().__init__(interval, logical_monitors, cursor=False, stale_after=stale_after)
        self.conn = connect()
        self.pid = os.getpid()
        self._turn = 0
        self._state = None
        self._pointer = None
        self.start()

    def _call(self, method, signature=None, body=()):
        msg = new_method_call(HELPER, method, signature, body)
        reply = self.conn.send_and_get_reply(msg, timeout=TIMEOUT)
        if reply.header.message_type == MessageType.error:
            # extension désactivée (écran verrouillé, désinstallée…) : jeepney ne lève pas
            raise RuntimeError(f"{method} : {reply.body[0] if reply.body else 'erreur D-Bus'}")
        return reply.body

    def read_native(self):
        x, y = self._call("GetPointer")
        self._pointer = (int(x), int(y))
        if self._state is None or self._turn % STATE_EVERY == 0:
            self._state = parse_state(self._call("GetState", "u", (self.pid,))[0])
        self._turn += 1
        return self._state

    def close_native(self):
        self.conn.close()

    def snapshot(self):
        snap = super().snapshot()
        native, pointer = self._native, self._pointer
        if native is None or pointer is None or self._stale():
            return snap
        logical = self._logical_monitors()
        mapper = CoordMapper(native.monitors, logical if len(logical) == len(native.monitors) else native.monitors)
        return WorldSnapshot(snap.monitors, snap.windows, mapper.point(*pointer))
