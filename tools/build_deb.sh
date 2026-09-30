#!/bin/bash
# Paquet Debian/Ubuntu à partir du build PyInstaller (pyinstaller felix.spec → dist/felix/).
#
#   tools/build_deb.sh 1.0.0      →  dist/virtual-felix_1.0.0_amd64.deb
#
# Contenu : /opt/virtual-felix (appli autonome), /usr/bin/virtual-felix, lanceur et icône,
# extension GNOME Shell « Felix Helper » installée pour tout le système (à activer par
# l'utilisateur : gnome-extensions enable felix-helper@kossolax.github.io, puis reconnexion
# sous Wayland). Les graphismes d'origine sont embarqués (voir CREDITS.md).
set -euo pipefail
VERSION="${1:?usage : tools/build_deb.sh VERSION}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -x dist/felix/felix ] || { echo "dist/felix/felix absent : lancez d'abord pyinstaller felix.spec" >&2; exit 1; }
[ -f dist/felix/_internal/assets/original/fig_100.png ] || { echo "le build n'embarque pas les graphismes d'origine" >&2; exit 1; }

PKG="build/deb/virtual-felix_${VERSION}_amd64"
EXT="felix-helper@kossolax.github.io"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/virtual-felix" "$PKG/usr/bin" "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/256x256/apps" "$PKG/usr/share/gnome-shell/extensions"
cp -a dist/felix/. "$PKG/opt/virtual-felix/"
ln -s /opt/virtual-felix/felix "$PKG/usr/bin/virtual-felix"
cp assets/icon/felix.png "$PKG/usr/share/icons/hicolor/256x256/apps/virtual-felix.png"
cp -r "gnome-extension/$EXT" "$PKG/usr/share/gnome-shell/extensions/"
cat > "$PKG/usr/share/applications/virtual-felix.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Virtual Felix
Comment=Le chat de bureau
Exec=/opt/virtual-felix/felix
Icon=virtual-felix
Categories=Game;Amusement;
EOF

cat > "$PKG/DEBIAN/control" <<EOF
Package: virtual-felix
Version: $VERSION
Section: games
Priority: optional
Architecture: amd64
Maintainer: kossolax <kossolax@users.noreply.github.com>
Installed-Size: $(du -sk "$PKG" | cut -f1)
Depends: libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0,
 libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libegl1, libgl1, libfontconfig1, libdbus-1-3
Homepage: https://github.com/kossolax/felix
Description: Virtual Felix, le chat de bureau
 Remake du ScreenMate Felix II (Felix, 1999-2000) : le chat marche sur
 la barre des tâches et les fenêtres, suit la souris, mange, boit et fait des
 bêtises. Fonctionne sous X11 et sous GNOME Wayland (avec l'extension fournie).
 Graphismes d'origine : AdTools et OgilvyOne Interactive pour Friskies Europe
 (voir /opt/virtual-felix/_internal/CREDITS.md).
EOF
for script in postinst postrm; do
    cat > "$PKG/DEBIAN/$script" <<'EOF'
#!/bin/sh
set -e
command -v gtk-update-icon-cache > /dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
command -v update-desktop-database > /dev/null && update-desktop-database -q /usr/share/applications || true
EOF
    chmod 0755 "$PKG/DEBIAN/$script"
done

chmod -R u=rwX,go=rX "$PKG"
chmod 0755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm" "$PKG/opt/virtual-felix/felix"
mkdir -p dist
dpkg-deb --build --root-owner-group "$PKG" "dist/virtual-felix_${VERSION}_amd64.deb"
