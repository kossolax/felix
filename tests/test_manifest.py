import pytest

from felix.core.manifest import load_manifest, parse_frames


def test_parse_frames_accepts_ranges_singletons_and_lists():
    assert parse_frames("0-3") == [0, 1, 2, 3]
    assert parse_frames("5") == [5]
    assert parse_frames("0-1,4,6-7") == [0, 1, 4, 6, 7]
    assert parse_frames([2, 1]) == [2, 1]


def bbox_all(sheet, rect):
    """Toute la cellule est opaque."""
    return (0, 0, rect[2], rect[3])


def test_frames_are_cells_of_the_sheet_grid_in_row_major_order():
    data = {"sheets": {"7": [2, 2]}, "animations": {"a": {"sheet": 7, "frames": "1-2", "fps": 10}}}
    anims = load_manifest(data, {7: (20, 10)}, bbox_all)
    assert [f.rect for f in anims["a"].frames] == [(10, 0, 10, 5), (0, 5, 10, 5)]


def test_fixed_anchor_is_first_frame_center_on_the_lowest_baseline():
    data = {"sheets": {"1": [2, 1]}, "animations": {"a": {"sheet": 1, "frames": "0-1", "fps": 10}}}
    boxes = {(0, 0, 10, 10): (2, 1, 6, 8), (10, 0, 10, 10): (4, 0, 9, 9)}
    anims = load_manifest(data, {1: (20, 10)}, lambda s, r: boxes[r])
    assert [f.anchor for f in anims["a"].frames] == [(4, 9), (4, 9)]


def test_track_anchor_follows_each_frame_bbox():
    data = {"sheets": {"1": [2, 1]},
            "animations": {"a": {"sheet": 1, "frames": "0-1", "fps": 10, "anchor": "track"}}}
    boxes = {(0, 0, 10, 10): (2, 1, 6, 8), (10, 0, 10, 10): (4, 0, 8, 9)}
    anims = load_manifest(data, {1: (20, 10)}, lambda s, r: boxes[r])
    assert [f.anchor for f in anims["a"].frames] == [(4, 8), (6, 9)]


def test_explicit_anchor_and_defaults():
    data = {"sheets": {"1": [1, 1]},
            "animations": {"a": {"sheet": 1, "frames": "0", "anchor": [3, 7], "shift": [12, 0]}}}
    a = load_manifest(data, {1: (10, 10)}, bbox_all)["a"]
    assert a.frames[0].anchor == (3, 7)
    assert (a.fps, a.loop, a.dx, a.shift, a.facing) == (10, False, 0, (12, 0), "front")


@pytest.mark.parametrize("anim", [
    {"sheet": 9, "frames": "0"},          # planche inconnue
    {"sheet": 1, "frames": "0-4"},        # hors de la grille 2×2
])
def test_invalid_animations_are_rejected(anim):
    data = {"sheets": {"1": [2, 2]}, "animations": {"bad": anim}}
    with pytest.raises(ValueError, match="bad"):
        load_manifest(data, {1: (20, 20)}, bbox_all)


def test_grid_must_divide_the_sheet():
    data = {"sheets": {"1": [3, 1]}, "animations": {}}
    with pytest.raises(ValueError, match="1"):
        load_manifest(data, {1: (20, 20)}, bbox_all)


def test_exit_point_becomes_the_end_shift_relative_to_the_anchor():
    data = {"sheets": {"1": [1, 1]},
            "animations": {"scene": {"sheet": 1, "frames": "0", "anchor": [80, 120], "exit": [30, 118]}}}
    a = load_manifest(data, {1: (200, 130)}, bbox_all)["scene"]
    assert a.shift == (-50, 0)
