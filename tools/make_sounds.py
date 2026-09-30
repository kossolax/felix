"""Génère assets/sounds/*.wav (outil de dev, ffmpeg requis pour les enregistrements).

- miaulements et ronronnement : enregistrements du domaine public / CC0 de
  Wikimedia Commons (voir assets/sounds/CREDITS.md), recoupés et normalisés ;
- croquettes (crunch) et lapement (lap) : synthétisés ici, sans source externe.
"""
import math
import random
import struct
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"
RATE = 22050
UA = {"User-Agent": "felix-desktop-pet/1.0 (https://github.com/kossolax/felix)"}
SOURCES = {
    "pleading": "https://upload.wikimedia.org/wikipedia/commons/6/6b/Meow_of_a_pleading_cat.oga",
    "young": "https://upload.wikimedia.org/wikipedia/commons/c/c0/Maullido_de_gata_hembra_joven.ogg",
    "purr": "https://upload.wikimedia.org/wikipedia/commons/4/4c/Purr_%2810_sec_loopable%29.ogg",
}
# (fichier, source, début, durée, gain en dB après normalisation)
CUTS = [
    ("meow1.wav", "young", 0.0, 1.2, 0),
    ("meow2.wav", "pleading", 3.55, 1.35, 0),
    ("meow3.wav", "pleading", 6.65, 1.0, 0),
    ("purr.wav", "purr", 0.0, 4.0, -9),  # un ronronnement est un bruit de fond
]


def write_wav(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples))


def lowpass(samples, alpha):
    out, prev = [], 0.0
    for s in samples:
        prev += alpha * (s - prev)
        out.append(prev)
    return out


def crunch(rng):
    """Croquettes : salves de bruit filtré à décroissance rapide."""
    total = [0.0] * int(RATE * 1.8)
    t = 0.05
    while t < 1.6:
        start, length = int(t * RATE), int(RATE * rng.uniform(0.04, 0.08))
        burst = lowpass([rng.uniform(-1, 1) for _ in range(length)], 0.35)
        for i, s in enumerate(burst):
            total[start + i] += s * math.exp(-i / (length / 5)) * rng.uniform(0.5, 0.9)
        t += rng.uniform(0.12, 0.25)
    return total


def lap(rng):
    """Lapement : petits « tlic » humides (bruit grave + blip descendant)."""
    total = [0.0] * int(RATE * 1.7)
    for k in range(5):
        start = int((0.08 + k * 0.3 + rng.uniform(-0.02, 0.02)) * RATE)
        length = int(RATE * 0.06)
        noise = lowpass([rng.uniform(-1, 1) for _ in range(length)], 0.12)
        for i in range(length):
            env = math.exp(-i / (length / 4))
            freq = 420 - 200 * i / length
            total[start + i] += env * (0.6 * noise[i] + 0.35 * math.sin(2 * math.pi * freq * i / RATE))
    return total


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1999)
    write_wav(OUT / "crunch.wav", crunch(rng))
    write_wav(OUT / "lap.wav", lap(rng))
    with tempfile.TemporaryDirectory() as tmp:
        for key, url in SOURCES.items():
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as resp:
                (Path(tmp) / key).write_bytes(resp.read())
        for name, key, start, duration, gain in CUTS:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(duration), "-i", str(Path(tmp) / key),
                 "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16",
                 "-af", f"loudnorm=I=-20:TP=-2,volume={gain}dB,afade=t=in:d=0.03,"
                        f"afade=t=out:st={duration - 0.2}:d=0.2",
                 str(OUT / name)], check=True)
    print(f"sons écrits dans {OUT}")


if __name__ == "__main__":
    sys.exit(main())
