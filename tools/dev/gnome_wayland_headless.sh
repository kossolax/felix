#!/bin/bash
# GNOME Shell Wayland « headless » isolé (bus D-Bus, config et données à part) avec l'extension
# Felix Helper, pour tester Felix sous Wayland sans quitter sa session.
#
#   tools/dev/gnome_wayland_headless.sh            démarre (Ctrl+C pour arrêter)
#   source /tmp/felix-wayland-test/env.sh          puis, dans un autre terminal :
#   python -m felix --debug-overlay                Felix dans ce GNOME
#   python3 tools/dev/wayland_screenshot.py out.png
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
T="${FELIX_TESTDIR:-/tmp/felix-wayland-test}"
rm -rf "$T"; mkdir -p "$T/data/gnome-shell/extensions" "$T/config"
cp -r "$ROOT/gnome-extension/felix-helper@kossolax.github.io" "$T/data/gnome-shell/extensions/"
export XDG_DATA_HOME="$T/data" XDG_CONFIG_HOME="$T/config" XDG_SESSION_TYPE=wayland
unset WAYLAND_DISPLAY DISPLAY
exec dbus-run-session -- bash -c "
  gsettings set org.gnome.shell disable-user-extensions false
  gsettings set org.gnome.shell enabled-extensions \"['felix-helper@kossolax.github.io']\"
  gsettings set org.gnome.shell welcome-dialog-last-shown-version '999'
  gsettings set org.gnome.mutter center-new-windows true
  # GNOME 46 démarre ses services X11 via systemd, absent de ce bus privé
  /usr/bin/python3 '$ROOT/tools/dev/fake_systemd.py' > '$T/fake_systemd.log' 2>&1 &
  sleep 1
  gnome-shell --headless --wayland --virtual-monitor 1600x900 --wayland-display=wayland-felix-test > '$T/shell.log' 2>&1 &
  until grep -q 'GNOME Shell started' '$T/shell.log' 2>/dev/null; do sleep 0.5; done
  XD=\$(grep -oE 'public X11 display :[0-9]+' '$T/shell.log' | grep -oE ':[0-9]+')
  cat > '$T/env.sh' <<ENV
export WAYLAND_DISPLAY=wayland-felix-test XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=GNOME
export DISPLAY=\$XD XAUTHORITY=\$(ls -t /run/user/\$(id -u)/.mutter-Xwaylandauth.* | head -1)
export DBUS_SESSION_BUS_ADDRESS=\$DBUS_SESSION_BUS_ADDRESS XDG_DATA_HOME='$T/data' XDG_CONFIG_HOME='$T/config'
ENV
  echo \"Prêt : source $T/env.sh\"
  wait"
