# Virtual Felix

Le chat de bureau de la fin des années 90 (*Felix II / Virtual Felix*, les ScreenMates offerts par Purina Felix), de retour sur **Linux (X11 et GNOME Wayland)** et **Windows 11**.

Il entre par sa chatière, se promène sur la barre des tâches ou le dock, saute et grimpe sur les fenêtres et les suit quand on les déplace. Il regarde la souris, la chasse et lui donne des coups de patte. On peut le nourrir, lui servir du lait ou le caresser pour qu'il ronronne. Il fait aussi des bêtises : traces de pattes sur l'écran, griffures, bocal à poisson rouge, télé, pelote de laine.

## Graphismes

Le dépôt **ne contient aucun graphisme d'origine**. Au premier lancement, ou via le script d'installation, Felix télécharge [`felix2.exe`](https://archive.org/details/felix2_virtualfelix) depuis archive.org, vérifie son empreinte SHA-256 et en extrait localement les sprites et l'icône.

Ces graphismes appartiennent à leurs ayants droit (Nestlé Purina, AdTools, Ogilvy). Ils ne servent ici qu'à un usage personnel. Ne redistribuez ni les sprites extraits ni l'exécutable Windows qui les embarque.

## Installation

### Linux (Ubuntu 24.04+, GNOME)

```bash
sudo apt install libxcb-cursor0          # requis par Qt 6
tools/install_linux.sh --autostart       # venv, sprites, menu des applications, démarrage auto, extension GNOME
```

- **Session X11** : rien d'autre à faire.
- **Session Wayland** (session par défaut d'Ubuntu, la seule à partir d'Ubuntu 25.10) :
  - l'appli tourne via XWayland ;
  - l'extension GNOME Shell *Felix Helper* lui montre les fenêtres et la souris ;
  - le script l'installe, mais GNOME ne la charge qu'**après une reconnexion** ;
  - Felix passe tout seul en mode complet dès qu'elle est active ;
  - sans elle, le chat marche seulement en bas de l'écran.

Pour un lancement manuel : `venv/bin/python -m felix`.

### Windows 11

La CI GitHub Actions produit à chaque push un artefact **felix-windows** : un dossier `felix/` avec `felix.exe`. Pour l'utiliser :

1. Téléchargez l'artefact depuis l'onglet *Actions* du dépôt.
2. Dézippez-le où vous voulez, puis lancez `felix.exe`.
3. Pour qu'il démarre avec Windows, cochez « Lancer au démarrage » dans son menu.

## Utilisation

| Geste | Effet |
|---|---|
| clic gauche sur le chat | caresse : il s'assoit et ronronne |
| glisser le chat | on l'attrape ; relâché en l'air, il tombe (et prend peur si c'est haut) |
| clic droit sur le chat | menu : Nourrir, Donner du lait, Jouer avec la pelote, Regarder la télé, jauges faim/soif, Rester immobile, Sons, Grande taille (×2), Lancer au démarrage, À propos, Quitter |

Le même menu est disponible dans la zone de notification quand le bureau en a une.

Faim et soif augmentent avec le temps, y compris quand Felix est fermé, avec un rattrapage plafonné à 48 h. Un chat affamé réclame en miaulant.

Journal : `~/.local/share/felix/felix.log` sous Linux, `%LOCALAPPDATA%\felix\felix.log` sous Windows. Pour plus de détails : `FELIX_LOG=DEBUG`.

## Architecture

```
felix/
  core/        cerveau du chat, physique, surfaces marchables, animations, faim/soif (Python pur, testé)
  render/      fenêtre du chat (Qt), accessoires, sons, superposition de débogage
  platform/    backends : x11 (python-xlib, événementiel), windows (ctypes/DWM),
               gnome_shell (D-Bus vers l'extension), degraded (écrans Qt seuls)
  resources/   lecture PE, décodage des images FIG2 des ScreenMates, PNG, recalage des planches
gnome-extension/felix-helper@kossolax.github.io/   extension GNOME Shell 45–50
sprites/felix.json                                 manifeste : grilles, animations, ancrages (pas de pixels)
```

Format FIG2, reconstitué pour ce projet :

- en-tête `FIG2` ;
- palette 256 × BGRx compressée en zlib ;
- pixels 8 bits compressés en zlib, lignes stockées de bas en haut ;
- l'index 253 (magenta) sert de couleur transparente.

## Développement

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python tools/extract_felix.py     # sprites dans assets/original/
QT_QPA_PLATFORM=offscreen venv/bin/pytest -q
venv/bin/python -m felix --debug-overlay   # dessine fenêtres détectées et surfaces marchables
venv/bin/python -m felix --probe           # état vu par le backend, en JSON
```

Outils :

- `tools/atlas_viewer.py` : lecture des animations et export des ancrages ;
- `tools/align.py` : recalage automatique des planches enchaînées ;
- `tools/make_sounds.py` : génération des sons ;
- `tools/dev/gnome_x11_xvfb.sh` : GNOME X11 sur un écran virtuel ;
- `tools/dev/gnome_wayland_headless.sh` : GNOME Wayland isolé, avec l'extension, pour tester sans quitter sa session ;
- `tools/dev/wayland_screenshot.py` : capture d'écran de ce GNOME Wayland.

## Crédits

- Felix II / Virtual Felix : ScreenMates d'AdTools et Ogilvy pour Purina Felix (1999–2000).
- Sons : Wikimedia Commons, CC0 et domaine public (détails dans `assets/sounds/CREDITS.md`).
