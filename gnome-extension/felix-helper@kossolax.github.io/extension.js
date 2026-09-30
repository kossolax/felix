// Felix Helper : expose sur le bus de session ce qu'un client Wayland ne peut pas voir,
// pour que Virtual Felix puisse marcher sur les fenêtres et suivre la souris.
//
//   io.github.felix.Helper  /io/github/felix/Helper  io.github.felix.Helper1
//     GetPointer() -> (ii)                 position du pointeur (coordonnées de la scène)
//     GetState(u exclude_pid) -> s         JSON : moniteurs, zones utiles, fenêtres du haut vers le bas
//     StateChanged(u serial)               émis (regroupé sur 40 ms) quand la pile de fenêtres change
//
// Lecture seule, géométrie uniquement : aucun titre ni contenu de fenêtre n'est exposé.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'io.github.felix.Helper';
const OBJECT_PATH = '/io/github/felix/Helper';
const IFACE_XML = `
<node>
  <interface name="io.github.felix.Helper1">
    <method name="GetPointer">
      <arg type="i" direction="out" name="x"/>
      <arg type="i" direction="out" name="y"/>
    </method>
    <method name="GetState">
      <arg type="u" direction="in" name="exclude_pid"/>
      <arg type="s" direction="out" name="state"/>
    </method>
    <signal name="StateChanged">
      <arg type="u" name="serial"/>
    </signal>
  </interface>
</node>`;

const KEPT_TYPES = [Meta.WindowType.NORMAL, Meta.WindowType.DIALOG, Meta.WindowType.MODAL_DIALOG];
const COALESCE_MS = 40;
const WINDOW_SIGNALS = ['position-changed', 'size-changed', 'notify::minimized', 'unmanaged'];

class Helper {
    GetPointer() {
        const [x, y] = global.get_pointer();
        return [x, y];
    }

    GetState(excludePid) {
        const display = global.display;
        const workspace = global.workspace_manager.get_active_workspace();
        const monitors = [];
        for (let i = 0; i < display.get_n_monitors(); i++) {
            const g = display.get_monitor_geometry(i);
            const wa = workspace.get_work_area_for_monitor(i);
            monitors.push({
                geometry: [g.x, g.y, g.width, g.height],
                workarea: [wa.x, wa.y, wa.width, wa.height],
                scale: display.get_monitor_scale(i),
            });
        }
        const windows = display.sort_windows_by_stacking(workspace.list_windows())
            .filter(w => !w.is_override_redirect() && KEPT_TYPES.includes(w.get_window_type()) &&
                !w.minimized && w.showing_on_its_workspace() && w.get_pid() !== excludePid)
            .reverse()
            .map(w => {
                const r = w.get_frame_rect();
                return {id: w.get_id(), rect: [r.x, r.y, r.width, r.height], fullscreen: w.is_fullscreen()};
            });
        return JSON.stringify({monitors, windows});
    }
}

export default class FelixHelperExtension extends Extension {
    enable() {
        this._serial = 0;
        this._pendingId = 0;
        this._globalSignals = [];
        this._windowSignals = new Map();

        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE_XML, new Helper());
        this._dbus.export(Gio.DBus.session, OBJECT_PATH);
        this._nameId = Gio.bus_own_name_on_connection(Gio.DBus.session, BUS_NAME,
            Gio.BusNameOwnerFlags.NONE, null, null);

        const display = global.display;
        const wm = global.workspace_manager;
        this._globalSignals.push([display, display.connect('restacked', () => this._changed())]);
        this._globalSignals.push([display, display.connect('window-created', (_d, win) => {
            this._track(win);
            this._changed();
        })]);
        this._globalSignals.push([wm, wm.connect('active-workspace-changed', () => this._changed())]);
        for (const actor of global.get_window_actors())
            this._track(actor.meta_window);
    }

    disable() {
        for (const [obj, id] of this._globalSignals)
            obj.disconnect(id);
        this._globalSignals = null;
        for (const [win, ids] of this._windowSignals)
            ids.forEach(id => win.disconnect(id));
        this._windowSignals = null;
        if (this._pendingId) {
            GLib.source_remove(this._pendingId);
            this._pendingId = 0;
        }
        Gio.bus_unown_name(this._nameId);
        this._dbus.unexport();
        this._dbus = null;
    }

    _track(win) {
        if (!win || this._windowSignals.has(win))
            return;
        const ids = WINDOW_SIGNALS.map(signal => win.connect(signal, () => {
            if (signal === 'unmanaged') {
                (this._windowSignals.get(win) ?? []).forEach(id => win.disconnect(id));
                this._windowSignals.delete(win);
            }
            this._changed();
        }));
        this._windowSignals.set(win, ids);
    }

    _changed() {
        if (this._pendingId)
            return;
        this._pendingId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, COALESCE_MS, () => {
            this._pendingId = 0;
            this._serial = (this._serial + 1) >>> 0;
            this._dbus?.emit_signal('StateChanged', new GLib.Variant('(u)', [this._serial]));
            return GLib.SOURCE_REMOVE;
        });
    }
}
