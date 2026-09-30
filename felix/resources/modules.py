"""Extensions de Felix II (catslikefelix.com, 2001-2002) : jouets, repas, chaton, bêtises.

Chacune était un installeur contenant une DLL (ressource MODULE/100) que Felix2.exe chargeait ;
ses planches FIG complètent celles du jeu. Leurs PNG sont livrés dans assets/original ; ce module
les régénère (tools/extract_felix.py) depuis la Wayback Machine ou archive.org, en vérifiant la DLL
(deux captures d'un même installeur diffèrent de quelques octets d'en-tête).
"""
import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from felix.resources.extract import _fetch
from felix.resources.fig import decode_fig2
from felix.resources.pe import read_resources
from felix.resources.png import encode_png

WAYBACK = "http://web.archive.org/web/{}id_/http://www.catslikefelix.com:80/felix_2_download/{}"
BUNBUNNY = ("https://archive.org/download/screenmates-collection-by-bunbunny.com/"
            "Screenmates%20Collection%20by%20Bunbunny.com.rar/Screenmates%20Collection%20by%20Bunbunny.com%2F{}")


@dataclass(frozen=True)
class Module:
    key: str
    title: str
    first_fig: int  # première planche : sa présence dit que l'extension est installée
    sha256: str  # de la DLL
    sources: tuple


MODULES = (
    Module("fun", "Fun and Games", 500, "fee06429594d3daa9badadfdf4c866440ad662e7779417559a2dd6807c7a7daf", (
        WAYBACK.format(20011212015311, "felix2funmoduleinstaller.exe"),
        WAYBACK.format(20010923075150, "felix2funmoduleinstaller.exe"),
        BUNBUNNY.format("Felix%20II%2FFun.exe"),
    )),
    Module("feeding", "Feeding", 600, "b7331976c7caf54f2bc631147779c04e99c8a3f4d525e7c6965007c4a5d8a455", (
        WAYBACK.format(20010701012624, "feed_felix.exe"),
        BUNBUNNY.format("felixfood.zip"),
    )),
    Module("kitten", "Kitten", 700, "dbcf3e0fb25eceb5a47592481678cb80ae24fbf904199851979513ff938e37e0", (
        WAYBACK.format(20010623040551, "Felix2KittenModuleInstaller.exe"),
        WAYBACK.format(20011212013612, "Felix2kittenModuleInstaller.exe"),
        BUNBUNNY.format("Felix%20II%2FKitten.exe"),
    )),
    Module("mischief", "Mischief", 800, "3b3ae5a1d4c40be1abc27de43bfb7cfb1736ead533539eb8b03fb2b579a6149c", (
        WAYBACK.format(20020207152526, "Felix2MischiefModuleInstaller.exe"),
        BUNBUNNY.format("Felix%20II%2FMis.exe"),
    )),
    Module("more_mischief", "More Mischief", 905, "e2e0ce4aa3172d7fb1131b0bda622cf3b86245d47eac3ed5fd97f0f51ffa85ff", (
        BUNBUNNY.format("Felix%20II%2FMis%202.exe"),
        BUNBUNNY.format("felixmoremischief.zip"),
    )),
)


def module_dll(blob):
    """La DLL d'une extension, depuis son installeur ou un zip qui le contient."""
    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for name in z.namelist():
                if name.lower().endswith(".exe"):
                    try:
                        return module_dll(z.read(name))
                    except ValueError:
                        continue
        raise ValueError("pas d'installeur d'extension dans ce zip")
    try:
        resources = read_resources(blob)
    except Exception as exc:
        raise ValueError(f"pas un exécutable Windows : {exc}") from exc
    dll = resources.get(("MODULE", 100))
    if dll is None:
        raise ValueError("pas d'extension Felix dans cet exécutable")
    return dll


def _extract(dll, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for (kind, name), blob in read_resources(dll).items():
        if kind == "FIG":
            img = decode_fig2(blob)
            (out_dir / f"fig_{name}.png").write_bytes(encode_png(img.width, img.height, img.rgba))


def _module(module, cache_dir, fetch):
    cached = cache_dir / f"{module.key}.dll"
    if cached.exists() and hashlib.sha256(cached.read_bytes()).hexdigest() == module.sha256:
        return cached.read_bytes()
    errors = []
    for url in module.sources:
        try:
            dll = module_dll(fetch(url))
        except (OSError, ValueError) as exc:
            errors.append(f"{url} : {exc}")
            continue
        if hashlib.sha256(dll).hexdigest() != module.sha256:
            errors.append(f"{url} : ce n'est pas la bonne extension")
            continue
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(dll)
        return dll
    raise OSError(f"extension « {module.title} » introuvable :\n" + "\n".join(errors))


def missing_modules(sprites_dir, modules=MODULES):
    return [m for m in modules if not (Path(sprites_dir) / f"fig_{m.first_fig}.png").exists()]


def install_modules(sprites_dir, cache_dir, modules=MODULES, fetch=_fetch):
    """Récupère et extrait les extensions : (clés installées, messages d'erreur)."""
    sprites_dir, cache_dir = Path(sprites_dir), Path(cache_dir)
    installed, errors = [], []
    for module in modules:
        try:
            _extract(_module(module, cache_dir, fetch), sprites_dir)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        installed.append(module.key)
    return installed, errors
