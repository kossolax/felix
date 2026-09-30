import hashlib
import struct
import zlib

import pytest

from felix.resources.extract import extract_images, verify_sha256
from tests.pe_builder import build_pe
from tests.test_fig import make_fig2


def make_launcher(figs):
    inner = build_pe({"FIG": figs, "XML": {100: b"<ICE9/>"}})
    return build_pe({"EXE": {100: struct.pack("<I", len(inner)) + zlib.compress(inner)}})


def test_extract_writes_one_png_per_fig(tmp_path):
    launcher = make_launcher({100: make_fig2(1, 1, [1]), 404: make_fig2(2, 1, [1, 1])})
    written = extract_images(launcher, tmp_path)
    assert sorted(p.name for p in written) == ["fig_100.png", "fig_404.png"]
    assert (tmp_path / "fig_100.png").read_bytes().startswith(b"\x89PNG")


def test_verify_sha256_rejects_other_file():
    data = b"felix"
    verify_sha256(data, hashlib.sha256(data).hexdigest())
    with pytest.raises(ValueError):
        verify_sha256(b"autre chose", hashlib.sha256(data).hexdigest())


def test_extract_also_writes_the_original_icon(tmp_path):
    from tests.test_icon import grp_icon, IMG_A
    inner = build_pe({"FIG": {100: make_fig2(1, 1, [1])}, 14: {100: grp_icon([(32, 32, len(IMG_A), 1)])},
                      3: {1: IMG_A}})
    launcher = build_pe({"EXE": {100: struct.pack("<I", len(inner)) + zlib.compress(inner)}})
    extract_images(launcher, tmp_path)
    assert (tmp_path / "felix.ico").read_bytes()[:4] == b"\0\0\1\0"


def test_download_falls_back_to_the_next_source(tmp_path):
    from felix.resources.extract import download
    good = b"le vrai felix2.exe"
    served = {"https://mort.example/felix2.exe": None,  # lien mort
              "https://faux.example/felix2.exe": b"autre chose",  # mauvais contenu
              "https://github.example/felix2.exe": good}
    calls = []

    def fetch(url):
        calls.append(url)
        if served[url] is None:
            raise OSError("404")
        return served[url]

    data = download(tmp_path / "felix2.exe", sources=list(served), sha256=hashlib.sha256(good).hexdigest(), fetch=fetch)
    assert data == good and calls == list(served)
    assert (tmp_path / "felix2.exe").read_bytes() == good


def test_download_fails_clearly_when_every_source_fails(tmp_path):
    from felix.resources.extract import download

    def fetch(url):
        raise OSError("hors ligne")

    with pytest.raises(OSError, match="felix2.exe"):
        download(tmp_path / "felix2.exe", sources=["https://a", "https://b"], sha256="0" * 64, fetch=fetch)


def test_corrupted_cache_is_replaced_by_a_fresh_download(tmp_path):
    from felix.resources.extract import download
    good = b"le vrai felix2.exe"
    cache = tmp_path / "felix2.exe"
    cache.write_bytes(b"tronque")
    data = download(cache, sources=["https://x"], sha256=hashlib.sha256(good).hexdigest(), fetch=lambda url: good)
    assert data == good and cache.read_bytes() == good
