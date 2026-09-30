#!/bin/bash
# GNOME Shell X11 sur un écran virtuel Xvfb (:99 par défaut), bus D-Bus privé.
#   tools/dev/gnome_x11_xvfb.sh        puis : DISPLAY=:99 python -m felix --debug-overlay
#   capture : import -display :99 -window root out.png
set -euo pipefail
NUM="${FELIX_XVFB:-99}"
Xvfb ":$NUM" -screen 0 1600x900x24 -nolisten tcp &
XPID=$!
trap 'kill $XPID' EXIT
sleep 1
export DISPLAY=":$NUM" XDG_SESSION_TYPE=x11
unset WAYLAND_DISPLAY
dbus-run-session -- gnome-shell --x11 --replace --sm-disable
