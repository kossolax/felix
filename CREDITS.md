# Crédits

## Graphismes : Virtual Felix 2 (*Felix II*, 1999-2000)

Les planches de sprites de `assets/original/` et l'icône d'origine viennent de **Virtual Felix 2**, le ScreenMate offert par la marque de nourriture pour chats Felix.

- D'après son écran « About Virtual Felix », il a été créé **pour Friskies Europe** (aujourd'hui Nestlé Purina PetCare) **par AdTools et OgilvyOne Interactive**.
  - **AdTools, Inc.** : la technologie *ScreenMates* (« Activated with AdTools technology »).
  - **OgilvyOne Interactive** (Ogilvy Interactive London) : l'agence.
- Site d'origine : www.catslikefelix.com.
- Felix et Friskies sont des marques de Nestlé.

Ses cinq extensions officielles, publiées sur catslikefelix.com en 2001-2002, complètent le jeu : *Fun and Games*, *Feeding*, *Kitten*, *Mischief* et *More Mischief*.

Les images sont reprises telles quelles. Seuls leur format change : FIG2 vers PNG, avec la couleur de transparence convertie en canal alpha. `python tools/extract_felix.py` les régénère à l'identique à partir des fichiers d'origine, qu'il vérifie par empreinte SHA-256.

Les animations elles-mêmes ont été reconstituées pour ce projet à partir des programmes d'origine, dans les manifestes de `sprites/` : découpage, cadences, ancrages et enchaînements.

## Préservation

Rien de tout cela ne serait encore disponible sans les personnes et services qui ont conservé ces programmes :

- **archive.org** : l'exécutable `felix2.exe` (item [`felix2_virtualfelix`](https://archive.org/details/felix2_virtualfelix)) et la [Screenmates Collection by Bunbunny.com](https://archive.org/details/screenmates-collection-by-bunbunny.com) ;
- la **Wayback Machine** d'archive.org : les captures des installeurs d'extensions de catslikefelix.com.

## Sons

Il n'y avait pas de sons dans Felix II. Ceux du projet sont des enregistrements CC0 ou du domaine public de Wikimedia Commons ; le détail est dans [`assets/sounds/CREDITS.md`](assets/sounds/CREDITS.md).

## Droits

**Virtual Felix** est un remake non officiel, gratuit et non commercial. Il n'a aucun lien avec Nestlé, Purina, Friskies, AdTools ou Ogilvy, qui ne l'ont ni approuvé ni soutenu.

- Les graphismes restent la propriété de leurs ayants droit. Ils sont inclus pour que le chat fonctionne sans rien télécharger.
- Ayants droit : ouvrez une [issue](https://github.com/kossolax/felix/issues) et ils seront retirés.

Mention de droits du programme d'origine (fenêtre « Copyright Info ») :

> All trade marks, copyright, database rights and/or all other intellectual property rights, in relation to all and any text, graphics and other material in whatever form contained on this site, are the property of Friskies Europe or its parent company or are used with the authorisation of the owner of such rights. This means that you may reproduce material on this site for personal use only. Unauthorised use, including but not limited to, modification, distribution, copying, renting, hiring, lending, transmission and broadcast of material on this site is prohibited. Material from this site may not be sold or otherwise distributed for profit.
