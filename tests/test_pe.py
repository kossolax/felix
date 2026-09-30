import pytest

from felix.resources.pe import read_resources
from tests.pe_builder import build_pe


def test_reads_resources_by_integer_type_and_id():
    exe = build_pe({3: {1: b"icon-bytes", 2: b"other"}})
    res = read_resources(exe)
    assert res[(3, 1)] == b"icon-bytes"
    assert res[(3, 2)] == b"other"


def test_reads_resources_by_string_type_and_name():
    exe = build_pe({"FIG": {100: b"FIG2...", "IDI_ICON": b"ico"}, "XML": {101: b"<RESL/>"}})
    res = read_resources(exe)
    assert res[("FIG", 100)] == b"FIG2..."
    assert res[("FIG", "IDI_ICON")] == b"ico"
    assert res[("XML", 101)] == b"<RESL/>"


def test_rejects_non_pe_data():
    with pytest.raises(ValueError):
        read_resources(b"not an executable at all" * 10)
