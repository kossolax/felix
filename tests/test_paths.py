import json

from felix.core.manifest import merge_manifests
from felix.paths import MANIFEST, ROOT, SPRITES, user_data_dir


def test_the_original_sheets_ship_with_the_code():
    """Le jeu et ses 5 extensions : toutes les planches sont dans le dépôt, rien à télécharger."""
    base = json.loads(MANIFEST.read_text(encoding="utf-8"))
    extras = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((MANIFEST.parent / "extensions").glob("*.json"))]
    assert len(extras) == 5
    sheets = merge_manifests(base, extras)["sheets"]
    missing = [key for key in sheets if not (SPRITES / f"fig_{key}.png").exists()]
    assert SPRITES == ROOT / "assets" / "original" and not missing


def test_the_credits_ship_with_the_sprites():
    credits = (ROOT / "CREDITS.md").read_text(encoding="utf-8")
    for who in ("Friskies Europe", "AdTools", "OgilvyOne Interactive", "Nestlé", "catslikefelix.com", "archive.org"):
        assert who in credits, who


def test_user_data_dir_per_platform(tmp_path):
    assert user_data_dir({"LOCALAPPDATA": str(tmp_path)}, "win32") == tmp_path / "felix"
    assert user_data_dir({"XDG_DATA_HOME": str(tmp_path)}, "linux") == tmp_path / "felix"
    assert user_data_dir({"HOME": str(tmp_path)}, "linux") == tmp_path / ".local" / "share" / "felix"
