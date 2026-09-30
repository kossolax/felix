"""Point d'entrée : python -m felix [--backend …] [--debug-overlay] [--probe] [--selftest]"""
import argparse
import json
import logging
import logging.handlers
import random
import sys

from felix.platform.detect import prepare_environment


def parse_args(argv):
    p = argparse.ArgumentParser(prog="felix", description="Virtual Felix, le chat de bureau.")
    p.add_argument("--backend", default="auto", choices=["auto", "x11", "windows", "gnome_shell", "degraded"])
    p.add_argument("--debug-overlay", action="store_true", help="dessine fenêtres et surfaces détectées")
    p.add_argument("--probe", action="store_true", help="affiche l'état vu par le backend (JSON) et quitte")
    p.add_argument("--selftest", action="store_true", help="fait tourner l'appli sans affichage réel et quitte")
    p.add_argument("--seed", type=int, help="graine du hasard (reproductibilité)")
    p.add_argument("--demo", default="", help=argparse.SUPPRESS)  # ex. feed,drink : scènes lancées au démarrage
    p.add_argument("--scale", type=int, choices=[1, 2], default=1, help=argparse.SUPPRESS)  # taille ×2 (tests)
    p.add_argument("--speed", type=float, default=1.0, help=argparse.SUPPRESS)  # temps accéléré (tests)
    return p.parse_args(argv)


def create_backend(name, session):
    import os
    from felix.platform.degraded import QtScreensBackend
    log = logging.getLogger("felix")
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen" and name != "degraded":
        log.info("plateforme Qt offscreen : backend dégradé")
        name = "degraded"
    factories = {
        "x11": ("felix.platform.x11", "X11Backend"),
        "windows": ("felix.platform.windows", "WindowsBackend"),
        "gnome_shell": ("felix.platform.gnome_shell", "GnomeShellBackend"),
    }
    if name in factories:
        module, cls = factories[name]
        try:
            return getattr(__import__(module, fromlist=[cls]), cls)()
        except Exception:
            log.exception("backend %s indisponible, repli sur le mode dégradé", name)
    return QtScreensBackend(cursor=session != "wayland")


def gnome_helper_available(session):
    if session == "windows":
        return False
    try:
        from felix.platform.gnome_shell import helper_available
    except ImportError:
        return False
    return helper_available()


def selftest(felix):
    felix.window.show()
    for _ in range(300):
        felix.tick(1 / 30)
    pet = felix.pet
    if pet.away:  # sorti par sa chatière : on l'appelle avant de le prendre
        pet.request("sit")
        for _ in range(60):
            felix.tick(1 / 30)
    pet.grab(pet.body.x, pet.body.y)
    pet.drag(pet.body.x, pet.body.y - 300)
    pet.release()
    landed = False
    for _ in range(120):  # il doit retomber sur ses pattes ; ce qu'il fait ensuite (grimper…) ne compte pas
        felix.tick(1 / 30)
        if pet.mode == "script" and pet.body.grounded:
            landed = True
            break
    log = logging.getLogger("felix")
    if not landed:
        from felix.platform.fake import scene_to_dict
        world = json.dumps(scene_to_dict(felix.backend.snapshot()))
        log.error("selftest : le chat n'a pas atterri (%s, scène %s, dehors %s, en (%.0f, %.0f) ; monde %s)",
                  pet.player.animation.name, pet.scene, pet.away, pet.body.x, pet.body.y, world)
        return 1
    message = f"selftest ok ({felix.backend.name}, {len(felix.bank.animations)} animations)"
    log.info(message)
    print(message)
    return 0


def setup_logging():
    """Journal dans le dossier utilisateur : l'exe Windows fenêtré n'a pas de console."""
    from felix.paths import user_data_dir
    handlers = []
    try:
        user_data_dir().mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(
            user_data_dir() / "felix.log", maxBytes=256_000, backupCount=2, encoding="utf-8"))
    except OSError:
        pass
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    import os
    level = getattr(logging, os.environ.get("FELIX_LOG", "INFO").upper(), logging.INFO)
    logging.basicConfig(level=level, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = lambda *exc: logging.getLogger("felix").critical("exception non gérée", exc_info=exc)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    setup_logging()
    session = prepare_environment()
    logging.getLogger("felix").info("démarrage (session %s, backend demandé %s)", session, args.backend)

    from PySide6.QtWidgets import QApplication, QMessageBox
    from felix.platform.detect import choose_backend

    app = QApplication(sys.argv[:1])
    app.setApplicationName("felix")
    from felix.paths import ROOT
    from PySide6.QtGui import QIcon
    app.setWindowIcon(QIcon(str(ROOT / "assets" / "icon" / "felix.png")))
    app.setQuitOnLastWindowClosed(False)

    backend = create_backend(choose_backend(session, args.backend, gnome_helper_available(session)), session)
    if args.probe:
        from felix.platform.fake import scene_to_dict
        if hasattr(backend, "wait_ready"):
            backend.wait_ready()
        print(json.dumps({"backend": backend.name, **scene_to_dict(backend.snapshot())}, indent=2))
        backend.stop()
        return 0

    from felix.paths import MANIFEST, SPRITES
    if not (SPRITES / "fig_100.png").exists():  # installation incomplète : jamais le cas d'un paquet
        logging.getLogger("felix").error("graphismes introuvables dans %s", SPRITES)
        if not args.selftest:
            QMessageBox.critical(None, "Felix", f"Graphismes introuvables dans {SPRITES} : réinstallez Felix.")
        backend.stop()
        return 2

    from felix.app import FelixApp
    from felix.render.sprites import SpriteBank

    from PySide6.QtCore import QSettings
    settings = QSettings("felix", "felix")

    def bank_loader(factor):
        return SpriteBank.load(MANIFEST, SPRITES, scale=factor)

    bank = bank_loader(args.scale)
    rng = random.Random(args.seed) if args.seed is not None else None
    upgrader = None
    if backend.name == "degraded" and session == "wayland" and args.backend == "auto":
        from felix.platform.detect import BackendUpgrader
        from felix.platform.gnome_shell import GnomeShellBackend
        upgrader = BackendUpgrader(lambda: gnome_helper_available(session), GnomeShellBackend)
    from felix.paths import SOUNDS
    from felix.render.sound import SoundPlayer
    sound = SoundPlayer(SOUNDS) if SOUNDS.exists() and not args.selftest else None
    felix = FelixApp(bank, backend, rng=rng, debug=args.debug_overlay, upgrader=upgrader, sound=sound,
                     settings=settings, bank_loader=bank_loader, speed=args.speed)
    if args.selftest:
        code = selftest(felix)
        backend.stop()
        return code
    for scene in filter(None, args.demo.split(",")):
        felix.pet.request(scene)
    felix.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
