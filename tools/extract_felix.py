"""Télécharge felix2.exe (archive.org) et extrait ses sprites dans assets/original/.

Usage : python tools/extract_felix.py [--out assets/original]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from felix.resources.extract import download, extract_images  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default=ROOT / "assets" / "cache" / "felix2.exe", type=Path)
    parser.add_argument("--out", default=ROOT / "assets" / "original", type=Path)
    args = parser.parse_args()
    written = extract_images(download(args.cache), args.out)
    print(f"{len(written)} planches écrites dans {args.out}")


if __name__ == "__main__":
    main()
