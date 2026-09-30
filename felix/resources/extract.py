"""Récupère Felix II sur archive.org et en extrait les planches de sprites en PNG."""
import hashlib
import urllib.request
from pathlib import Path

from felix.resources.fig import decode_fig2, unpack_launcher
from felix.resources.pe import read_resources
from felix.resources.png import encode_png

SOURCE_URL = "https://archive.org/download/felix2_virtualfelix/felix2.exe"
SOURCE_SHA256 = "d023921f009438eb902dcdb7f2136851a85f4944af325fcc6cf12b502ae32387"


def verify_sha256(data, expected):
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise ValueError(f"sha256 inattendu : {digest}")


def download(cache_file, url=SOURCE_URL, sha256=SOURCE_SHA256):
    cache_file = Path(cache_file)
    if cache_file.exists():
        data = cache_file.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
    verify_sha256(data, sha256)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(data)
    return data


def extract_images(launcher, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for (kind, name), blob in read_resources(unpack_launcher(launcher)).items():
        if kind != "FIG":
            continue
        img = decode_fig2(blob)
        path = out_dir / f"fig_{name}.png"
        path.write_bytes(encode_png(img.width, img.height, img.rgba))
        written.append(path)
    return written
