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
