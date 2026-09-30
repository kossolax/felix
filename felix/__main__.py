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
    return p.parse_args(argv)


def ensure_sprites(interactive):
    from felix.paths import find_sprites_dir, user_data_dir
    found = find_sprites_dir()
    if found or not interactive:
        return found
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt
    target = user_data_dir() / "original"
    answer = QMessageBox.question(
        None, "Felix",
        "Les graphismes d'origine de Felix ne sont pas encore installés.\n\n"
        "Les télécharger depuis archive.org (felix2.exe, 758 Ko) et les extraire dans\n"
        f"{target} ?")
    if answer != QMessageBox.StandardButton.Yes:
        return None
    from felix.resources.extract import download, extract_images
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        extract_images(download(user_data_dir() / "cache" / "felix2.exe"), target)
    finally:
        QApplication.restoreOverrideCursor()
    return find_sprites_dir()


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
    pet.grab(pet.body.x, pet.body.y)
    pet.drag(pet.body.x, pet.body.y - 300)
    pet.release()
    for _ in range(120):
        felix.tick(1 / 30)
    log = logging.getLogger("felix")
    if not pet.body.grounded:
        log.error("selftest : le chat n'a pas atterri")
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
    logging.basicConfig(level=logging.INFO, handlers=handlers,
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
    app.setQuitOnLastWindowClosed(False)

    backend = create_backend(choose_backend(session, args.backend, gnome_helper_available(session)), session)
    if args.probe:
        from felix.platform.fake import scene_to_dict
        if hasattr(backend, "wait_ready"):
            backend.wait_ready()
        print(json.dumps({"backend": backend.name, **scene_to_dict(backend.snapshot())}, indent=2))
        backend.stop()
        return 0

    sprites = ensure_sprites(interactive=not args.selftest)
    if sprites is None:
        if not args.selftest:
            QMessageBox.information(None, "Felix", "Pas de graphismes : Felix ne peut pas démarrer.")
        backend.stop()
        return 2

    from felix.app import FelixApp
    from felix.paths import MANIFEST
    from felix.render.sprites import SpriteBank

    bank = SpriteBank.load(MANIFEST, sprites)
    rng = random.Random(args.seed) if args.seed is not None else None
    upgrader = None
    if backend.name == "degraded" and session == "wayland" and args.backend == "auto":
        from felix.platform.detect import BackendUpgrader
        from felix.platform.gnome_shell import GnomeShellBackend
        upgrader = BackendUpgrader(lambda: gnome_helper_available(session), GnomeShellBackend)
    felix = FelixApp(bank, backend, rng=rng, debug=args.debug_overlay, upgrader=upgrader)
    if args.selftest:
        code = selftest(felix)
        backend.stop()
        return code
    felix.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
