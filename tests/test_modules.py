"""Extensions de Felix II (2001-2002) : un installeur qui contient une DLL (MODULE/100) et ses planches."""
import hashlib
import io
import zipfile

import pytest

from felix.resources.modules import MODULES, Module, install_modules, missing_modules, module_dll
from tests.pe_builder import build_pe
from tests.test_fig import make_fig2


def make_dll(first=500):
    return build_pe({"FIG": {first: make_fig2(1, 1, [1]), first + 1: make_fig2(2, 1, [1, 1])},
                     "TXT": {100: b"Fun and Games"}})


def installer(dll):
    return build_pe({"MODULE": {100: dll}})


def zipped(blob, name="felix_food.exe"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", b"hello")
        z.writestr(name, blob)
    return buf.getvalue()


def module(dll, sources, key="fun", first=500):
    return Module(key, "Fun and Games", first, hashlib.sha256(dll).hexdigest(), tuple(sources))


def test_the_module_dll_is_found_in_an_installer_or_a_zip():
    dll = make_dll()
    assert module_dll(installer(dll)) == dll
    assert module_dll(zipped(installer(dll))) == dll
    with pytest.raises(ValueError):
        module_dll(b"rien du tout")


def test_installing_a_module_extracts_its_sheets(tmp_path):
    dll = make_dll()
    m = module(dll, ["https://a"])
    assert missing_modules(tmp_path / "sprites", [m]) == [m]
    installed, errors = install_modules(tmp_path / "sprites", tmp_path / "cache", [m], fetch=lambda url: installer(dll))
    assert installed == ["fun"] and errors == []
    assert (tmp_path / "sprites" / "fig_500.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "sprites" / "fig_501.png").exists()
    assert missing_modules(tmp_path / "sprites", [m]) == []


def test_any_capture_of_the_installer_will_do_if_its_module_is_the_right_one(tmp_path):
    # deux captures d'un même installeur diffèrent de quelques octets : c'est la DLL qu'on vérifie
    dll = make_dll()
    m = module(dll, ["https://mort", "https://faux", "https://bon"])
    served = {"https://mort": None, "https://faux": installer(make_dll(600)), "https://bon": zipped(installer(dll))}
    calls = []

    def fetch(url):
        calls.append(url)
        if served[url] is None:
            raise OSError("404")
        return served[url]

    installed, errors = install_modules(tmp_path / "s", tmp_path / "c", [m], fetch=fetch)
    assert installed == ["fun"] and errors == [] and calls == list(served)


def test_a_module_out_of_reach_is_reported_and_the_others_still_installed(tmp_path):
    good = make_dll(500)
    ms = [module(good, ["https://ok"]), Module("feeding", "Feeding", 600, "0" * 64, ("https://ko",))]
    installed, errors = install_modules(tmp_path / "s", tmp_path / "c", ms, fetch=lambda url: installer(good))
    assert installed == ["fun"]
    assert len(errors) == 1 and "Feeding" in errors[0]


def test_a_downloaded_module_is_kept_in_the_cache(tmp_path):
    dll = make_dll()
    m = module(dll, ["https://a"])
    calls = []

    def fetch(url):
        calls.append(url)
        return installer(dll)

    install_modules(tmp_path / "s", tmp_path / "c", [m], fetch=fetch)
    (tmp_path / "s" / "fig_500.png").unlink()
    install_modules(tmp_path / "s", tmp_path / "c", [m], fetch=fetch)
    assert calls == ["https://a"] and (tmp_path / "s" / "fig_500.png").exists()


def test_the_five_extensions_of_felix_ii():
    assert [m.key for m in MODULES] == ["fun", "feeding", "kitten", "mischief", "more_mischief"]
    assert [m.first_fig for m in MODULES] == [500, 600, 700, 800, 905]
    assert all(len(m.sha256) == 64 and m.sources for m in MODULES)


def test_missing_extensions_are_fetched_in_the_background(qapp):
    import threading
    from PySide6.QtCore import QCoreApplication
    from felix.extensions import ExtensionFetcher
    threads, results = [], []

    def install():
        threads.append(threading.current_thread())
        return ["fun"], ["Kitten : hors ligne"]

    fetcher = ExtensionFetcher(install)
    fetcher.finished.connect(lambda installed, errors: results.append((installed, errors)))
    fetcher.start()
    for _ in range(200):
        QCoreApplication.processEvents()
        if results:
            break
        threading.Event().wait(0.01)
    assert results == [(["fun"], ["Kitten : hors ligne"])]
    assert threads and threads[0] is not threading.main_thread()
