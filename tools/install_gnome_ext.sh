#!/bin/bash
# Installe (ou met à jour) l'extension GNOME Shell « Felix Helper », nécessaire sous Wayland.
#   tools/install_gnome_ext.sh            installe et active
#   tools/install_gnome_ext.sh --remove   désactive et supprime
set -euo pipefail
UUID="felix-helper@kossolax.github.io"
SRC="$(cd "$(dirname "$0")/.." && pwd)/gnome-extension/$UUID"

if [ "${1:-}" = "--remove" ]; then
    gnome-extensions disable "$UUID" 2>/dev/null || true
    gnome-extensions uninstall "$UUID" 2>/dev/null || true
    echo "Extension $UUID supprimée."
    exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
gnome-extensions pack "$SRC" --force --out-dir "$TMP"
gnome-extensions install --force "$TMP/$UUID.shell-extension.zip"

if gnome-extensions enable "$UUID" 2>/dev/null; then
    echo "Extension $UUID installée et activée."
else
    echo "Extension $UUID installée."
    if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
        echo "Sous Wayland, GNOME ne la charge qu'après une reconnexion :"
        echo "  déconnectez-vous puis reconnectez-vous, puis lancez : gnome-extensions enable $UUID"
    else
        echo "Rechargez GNOME Shell (Alt+F2, r, Entrée) puis : gnome-extensions enable $UUID"
    fi
fi
