"""Récupère felix2.exe (archive.org, sinon la copie des releases GitHub) et extrait ses sprites.

Usage : python tools/extract_felix.py [--from felix2.exe] [--out assets/original]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from felix.resources.extract import SOURCE_SHA256, download, extract_images, verify_sha256  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default=ROOT / "assets" / "cache" / "felix2.exe", type=Path)
    parser.add_argument("--out", default=ROOT / "assets" / "original", type=Path)
    parser.add_argument("--from", dest="source", type=Path, help="felix2.exe déjà téléchargé")
    args = parser.parse_args()
    if args.source:
        data = args.source.read_bytes()
        verify_sha256(data, SOURCE_SHA256)
    else:
        data = download(args.cache)
    written = extract_images(data, args.out)
    print(f"{len(written)} planches écrites dans {args.out}")


if __name__ == "__main__":
    main()
