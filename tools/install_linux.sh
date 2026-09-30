#!/bin/bash
# Installation de Virtual Felix pour l'utilisateur courant (Ubuntu / GNOME).
#
#   tools/install_linux.sh [--autostart] [--no-extension]
#
# - crée venv/ et installe les dépendances Python ;
# - télécharge felix2.exe depuis archive.org et en extrait les sprites (usage personnel) ;
# - ajoute « Virtual Felix » au menu des applications ;
# - sous GNOME, installe l'extension Felix Helper (indispensable sous Wayland) ;
# - --autostart : lance Felix à l'ouverture de session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
AUTOSTART=0
EXTENSION=1
for arg in "$@"; do
    case "$arg" in
        --autostart) AUTOSTART=1 ;;
        --no-extension) EXTENSION=0 ;;
        *) echo "option inconnue : $arg" >&2; exit 2 ;;
    esac
done

python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10 ou plus requis." >&2; exit 1; }
if command -v dpkg > /dev/null && ! dpkg -s libxcb-cursor0 > /dev/null 2>&1; then
    echo "Qt 6 a besoin de libxcb-cursor0 :  sudo apt install libxcb-cursor0"
fi

echo "→ environnement Python (venv/)"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "→ graphismes d'origine (archive.org, felix2.exe, 758 Ko)"
venv/bin/python tools/extract_felix.py

echo "→ lanceur dans le menu des applications"
ICON="$ROOT/assets/original/felix.png"
QT_QPA_PLATFORM=offscreen venv/bin/python - "$ICON" <<'EOF'
import sys
from PySide6.QtGui import QGuiApplication, QImage
app = QGuiApplication([])
QImage("assets/original/felix.ico").scaled(64, 64).save(sys.argv[1])
EOF
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
cat > "$APPS/virtual-felix.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Virtual Felix
Comment=Le chat de bureau
Exec=$ROOT/venv/bin/python -m felix
Path=$ROOT
Icon=$ICON
Categories=Amusement;
EOF

if [ "$AUTOSTART" = 1 ]; then
    echo "→ lancement à l'ouverture de session"
    venv/bin/python -c "from felix import autostart; autostart.enable()"
fi

if [ "$EXTENSION" = 1 ] && [[ "${XDG_CURRENT_DESKTOP:-}" == *GNOME* ]] && command -v gnome-extensions > /dev/null; then
    echo "→ extension GNOME Shell « Felix Helper » (le chat voit les fenêtres sous Wayland)"
    tools/install_gnome_ext.sh || echo "  (extension non installée : Felix marchera seulement en bas de l'écran sous Wayland)"
fi

echo "Terminé. Lancez « Virtual Felix » depuis le menu, ou : $ROOT/venv/bin/python -m felix"
