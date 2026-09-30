import os
import random
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_selftest_runs_the_whole_app_headless(tmp_path):
    # dossiers utilisateur temporaires : ni journal ni réglages réels touchés
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_DATA_HOME=str(tmp_path / "data"),
               XDG_CONFIG_HOME=str(tmp_path / "config"), LOCALAPPDATA=str(tmp_path / "local"))
    out = subprocess.run([sys.executable, "-m", "felix", "--selftest"], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "selftest ok" in out.stdout
    assert "6 sons" in out.stdout  # QtMultimedia charge les sons (le paquet n'embarque que le nécessaire)


def test_selftest_calls_back_a_cat_that_went_out(qapp, tmp_path):
    from PySide6.QtCore import QSettings
    from felix.__main__ import selftest
    from felix.app import FelixApp
    from felix.core.world import Monitor, Rect, WorldSnapshot
    from felix.paths import MANIFEST
    from felix.platform.fake import FakeBackend
    from felix.render.sprites import SpriteBank
    bank = SpriteBank.load(MANIFEST, ROOT / "assets" / "original")
    snap = WorldSnapshot(monitors=(Monitor(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1080)),))
    settings = QSettings(str(tmp_path / "felix.ini"), QSettings.Format.IniFormat)
    felix = FelixApp(bank, FakeBackend(snap), settings=settings)
    felix.pet.request("outing")  # il sera dehors quand le selftest voudra le prendre
    assert selftest(felix) == 0


def test_a_failed_selftest_says_what_the_cat_and_the_backend_were_doing(qapp, tmp_path, caplog):
    from PySide6.QtCore import QSettings
    from felix.__main__ import selftest
    from felix.app import FelixApp
    from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
    from felix.paths import MANIFEST, SPRITES
    from felix.platform.fake import FakeBackend
    from felix.render.sprites import SpriteBank
    bank = SpriteBank.load(MANIFEST, SPRITES)
    screen = Rect(0, 0, 1024, 768)
    video = WinRect(7, screen, fullscreen=True)  # le chat se cache et se fige derrière une vidéo
    snap = WorldSnapshot(monitors=(Monitor(screen, screen),), windows=(video,))
    settings = QSettings(str(tmp_path / "felix.ini"), QSettings.Format.IniFormat)
    felix = FelixApp(bank, FakeBackend(snap), settings=settings)
    assert selftest(felix) == 1
    message = caplog.records[-1].getMessage()
    assert "fall_" in message and '"fullscreen": true' in message


def test_selftest_passes_when_the_landed_cat_goes_on_to_climb_a_window(qapp, tmp_path):
    """Échec intermittent de la CI Windows : le chat avait bien atterri, puis grimpait sur la fenêtre
    de la console (« climb », pas posé) quand le selftest regardait, 4 s après l'avoir lâché."""
    from PySide6.QtCore import QSettings
    from felix.__main__ import selftest
    from felix.app import FelixApp
    from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot
    from felix.paths import MANIFEST, SPRITES
    from felix.platform.fake import FakeBackend
    from felix.render.sprites import SpriteBank
    bank = SpriteBank.load(MANIFEST, SPRITES)
    console = WinRect(131396, Rect(25, 26, 1030, 628))  # le monde relevé par le selftest en échec
    snap = WorldSnapshot(monitors=(Monitor(Rect(0, 0, 1024, 768), Rect(0, 0, 1024, 720)),), windows=(console,),
                         cursor=(512, 384))
    settings = QSettings(str(tmp_path / "felix.ini"), QSettings.Format.IniFormat)
    felix = FelixApp(bank, FakeBackend(snap), settings=settings, rng=random.Random(0))
    pet = felix.pet
    real_pick, real_release = pet.temper.pick, pet.release

    def release():  # une fois lâché, il grimpe dès qu'il peut
        real_release()
        pet.temper.pick = lambda choices: "climb" if "climb" in choices else real_pick(choices)

    pet.release = release
    assert selftest(felix) == 0
