# Virtual Felix

Le chat de bureau de la fin des années 90 (*Felix II / Virtual Felix*, les ScreenMates offerts par Purina Felix), de retour sur **Linux (X11 et GNOME Wayland)** et **Windows 11**.

Il entre par sa chatière (et sort parfois se promener), se promène sur la barre des tâches ou le dock, saute et grimpe sur les fenêtres et les suit quand on les déplace. Au bout d'une fenêtre, il regarde en bas, puis saute ou recule. Il regarde la souris, la chasse et lui donne des coups de patte. On peut le nourrir (il entre dans le placard à pâtée, pousse la porte en mangeant et passe la tête entre les boîtes), lui servir du lait qu'il lape par terre, ou le caresser pour qu'il ronronne. Il fait aussi des bêtises : traces de pattes sur l'écran, griffures, bocal où nage un poisson rouge qu'il regarde, le nez collé à la vitre, télé, pelote de laine. La pelote est un vrai objet qui roule, rebondit et tombe des fenêtres : le chat la guette, bondit dessus, la tapote et la renvoie d'un coup de patte, plusieurs fois, jusqu'à ce qu'elle se déroule et s'en aille. On peut l'attraper et la lancer à la souris, il court après. Sa boîte à jouets peut rester posée sur le bureau. Les extensions de 2001-2002 sont récupérées toutes seules au premier lancement : avec *Feeding*, on lui tend au bout du curseur une boîte de pâtée, une brique de lait ou un sachet de friandises (clic gauche pour servir, clic droit pour reprendre) ; avec *Kitten*, un chaton apparaît, boit du lait avec lui, le suit partout, joue avec sa queue, se fait porter par la peau du cou et n'arrive pas à passer la chatière ; avec *Fun and Games*, il tapote un ballon de plage puis le crève en bondissant dessus, attrape une souris mécanique et joue avec, et chasse une grenouille qui lui échappe toujours ; avec *Mischief*, il fait ses griffes sur la vitre, renverse une plante en pot et fouille la corbeille ; avec *More Mischief*, il déchire l'écran pour s'y cacher, joue avec un papillon posé sur son nez et plonge dans un tas de feuilles mortes. Son humeur varie : fatigué, il somnole ; en forme, il fait des bêtises, sans répéter sans cesse la même chose.

## Téléchargement

Les paquets sont sur la page [Releases](https://github.com/kossolax/felix/releases) :

- **Ubuntu 24.04+** : `virtual-felix_X.Y.Z_amd64.deb`, à installer avec `sudo apt install ./virtual-felix_X.Y.Z_amd64.deb`. On lance ensuite « Virtual Felix » depuis le menu des applications. Sous Wayland, il faut aussi activer l'extension fournie : `gnome-extensions enable felix-helper@kossolax.github.io`, puis se reconnecter.
- **Windows 10/11** : `virtual-felix-X.Y.Z-windows-x64.zip`. On le dézippe, puis on lance `felix\felix.exe`.

Publier une version : `git tag vX.Y.Z && git push origin vX.Y.Z`. Le workflow `release` construit, teste et publie les deux paquets.

## Graphismes

Le dépôt et les paquets **ne contiennent aucun graphisme d'origine**. Au premier lancement, Felix propose trois moyens de récupérer `felix2.exe` :

- le télécharger depuis [archive.org](https://archive.org/details/felix2_virtualfelix) ;
- sinon, le télécharger depuis la copie de secours de la release [`original-felix2`](https://github.com/kossolax/felix/releases/tag/original-felix2) (téléchargement automatique seulement si le dépôt est public) ;
- choisir un exemplaire déjà présent sur la machine.

Il vérifie ensuite l'empreinte SHA-256 du fichier et en extrait localement les sprites.

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

Prenez le zip de la dernière release, dézippez-le, puis lancez `felix\felix.exe`. Pour qu'il démarre avec Windows, cochez « Lancer au démarrage » dans son menu. La CI produit aussi un artefact **felix-windows** à chaque push.

## Utilisation

| Geste | Effet |
|---|---|
| clic gauche sur le chat | caresse : il s'assoit et ronronne |
| glisser le chat | on l'attrape ; relâché en l'air, il tombe (et prend peur si c'est haut) |
| clic droit sur le chat | menu : À manger ▸ (Nourrir, Donner du lait, et avec l'extension : Pâtée, Lait et Friandises Felix), Jouer ▸ (pelote, et avec l'extension : ballon, souris mécanique, grenouille ; télé, poisson rouge), Montrer / Cacher le chaton (extension), jauges faim/soif, Rester immobile, Sons, Boîte à jouets, Lancer au démarrage, À propos, Quitter (le chat sort par sa chatière) |
| boîte à jouets | glisser pour la déplacer ; clic droit : Jouer avec la pelote (elle bondit hors de la boîte), Ranger la boîte à jouets |
| pelote | glisser puis lâcher pour la lancer (le chat court après) ; la poser sur sa boîte pour la ranger |

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
- `tools/record_scene.py` : enregistrement hors écran d'une scène, image par image, en planche contact ;
- `tools/make_sounds.py` : génération des sons ;
- `tools/make_icon.py` : dessin de l'icône ;
- `tools/build_deb.sh` : construction du paquet Debian ;
- `tools/dev/gnome_x11_xvfb.sh` : GNOME X11 sur un écran virtuel ;
- `tools/dev/gnome_wayland_headless.sh` : GNOME Wayland isolé, avec l'extension, pour tester sans quitter sa session ;
- `tools/dev/wayland_screenshot.py` : capture d'écran de ce GNOME Wayland.

## Crédits

- Felix II / Virtual Felix : ScreenMates d'AdTools et Ogilvy pour Purina Felix (1999–2000).
- Sons : Wikimedia Commons, CC0 et domaine public (détails dans `assets/sounds/CREDITS.md`).
