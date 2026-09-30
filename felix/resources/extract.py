"""Récupère Felix II sur archive.org et en extrait les planches de sprites en PNG."""
import hashlib
import urllib.request
from pathlib import Path

from felix.resources.fig import decode_fig2, unpack_launcher
from felix.resources.icon import build_ico
from felix.resources.pe import read_resources
from felix.resources.png import encode_png

SOURCES = [
    "https://archive.org/download/felix2_virtualfelix/felix2.exe",
    # copie de secours dans les releases du projet (accessible sans compte si le dépôt est public)
    "https://github.com/kossolax/felix/releases/download/original-felix2/felix2.exe",
]
SOURCE_SHA256 = "d023921f009438eb902dcdb7f2136851a85f4944af325fcc6cf12b502ae32387"
USER_AGENT = "felix-desktop-pet/1.0 (https://github.com/kossolax/felix)"


def verify_sha256(data, expected):
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise ValueError(f"sha256 inattendu : {digest}")


def _fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as resp:
        return resp.read()


def download(cache_file, sources=SOURCES, sha256=SOURCE_SHA256, fetch=_fetch):
    """Renvoie le contenu de felix2.exe : depuis le cache, sinon depuis la première source valide."""
    cache_file = Path(cache_file)
    if cache_file.exists():
        data = cache_file.read_bytes()
        try:
            verify_sha256(data, sha256)
            return data
        except ValueError:
            cache_file.unlink()  # cache abîmé (téléchargement interrompu…) : on recommence
    errors = []
    for url in sources:
        try:
            data = fetch(url)
            verify_sha256(data, sha256)
        except (OSError, ValueError) as exc:
            errors.append(f"{url} : {exc}")
            continue
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(data)
        return data
    raise OSError("impossible de récupérer felix2.exe :\n" + "\n".join(errors))


def extract_images(launcher, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    resources = read_resources(unpack_launcher(launcher))
    ico = build_ico(resources)
    if ico:
        (out_dir / "felix.ico").write_bytes(ico)
    for (kind, name), blob in resources.items():
        if kind != "FIG":
            continue
        img = decode_fig2(blob)
        path = out_dir / f"fig_{name}.png"
        path.write_bytes(encode_png(img.width, img.height, img.rgba))
        written.append(path)
    return written
