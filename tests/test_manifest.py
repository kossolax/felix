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


def test_marks_are_converted_to_sheet_rects_of_the_last_frame():
    data = {"sheets": {"1": [2, 1]},
            "animations": {"a": {"sheet": 1, "frames": "0-1", "marks": [[3, 4, 5, 6]]}}}
    a = load_manifest(data, {1: (40, 20)}, bbox_all)["a"]
    # dernière image = cellule (20, 0) : marque à (23, 4) dans la planche, et (3, 4) dans la cellule
    assert a.marks == (((23, 4, 5, 6), (3, 4)),)


def test_scale_multiplies_every_coordinate():
    data = {"sheets": {"1": [2, 1]},
            "animations": {"a": {"sheet": 1, "frames": "0-1", "anchor": [3, 7], "dx": 4,
                                 "exit": [5, 7], "marks": [[1, 2, 3, 4]]}}}
    one = load_manifest(data, {1: (20, 10)}, bbox_all)["a"]
    two = load_manifest(data, {1: (40, 20)}, bbox_all, scale=2)["a"]
    assert two.frames[1].rect == tuple(2 * v for v in one.frames[1].rect)
    assert two.frames[0].anchor == (6, 14)
    assert (two.dx, two.shift) == (8, (4, 0))
    assert two.marks == (((2 * 10 + 2, 4, 6, 8), (2, 4)),)


def compose_data(loop=True):
    return {"sheets": {"1": [2, 1], "2": [3, 1]},
            "animations": {
                "cat": {"sheet": 1, "frames": "0-1", "fps": 6, "loop": True, "anchor": [5, 9]},
                "tv": {"sheet": 2, "frames": "0-2", "fps": 3, "loop": True},
                "watch": {"compose": {"base": "cat", "under": "tv", "at": [60, -44]}, "fps": 6, "loop": loop}}}


def test_compose_draws_a_second_animation_under_the_first():
    a = load_manifest(compose_data(), {1: (20, 10), 2: (30, 10)}, bbox_all)["watch"]
    # chat 2 images à 6 i/s, télé 3 images à 3 i/s (2 ticks chacune) : cycle ppcm(2, 6) = 6
    assert len(a.frames) == 6 and a.loop and a.fps == 6
    cats = [f.rect[0] for f in a.frames]
    tvs = [f.under[0][1][0] for f in a.frames]
    assert cats == [0, 10, 0, 10, 0, 10]
    assert tvs == [0, 0, 10, 10, 20, 20]
    assert a.frames[0].anchor == (5, 9) and a.frames[0].under[0][2] == (60, -44)


def test_one_shot_compose_follows_the_under_animation():
    a = load_manifest(compose_data(loop=False), {1: (20, 10), 2: (30, 10)}, bbox_all)["watch"]
    assert len(a.frames) == 6 and not a.loop


def test_frame_bounds_include_the_layers():
    from felix.core.anim import frame_bounds
    a = load_manifest(compose_data(), {1: (20, 10), 2: (30, 10)}, bbox_all)["watch"]
    assert frame_bounds(a.frames[0]) == (0, -44, 70, 10)  # cellule 10×10 + télé 10×10 en (60, -44)


def test_compose_can_draw_a_layer_over_the_base():
    data = compose_data()
    data["animations"]["watch"]["compose"] = {"base": "cat", "over": "tv", "over_at": [3, 4]}
    a = load_manifest(data, {1: (20, 10), 2: (30, 10)}, bbox_all)["watch"]
    assert len(a.frames) == 6 and a.frames[0].under == ()
    assert [f.over[0][1][0] for f in a.frames] == [0, 0, 10, 10, 20, 20]
    assert a.frames[0].over[0][2] == (3, 4)


def test_compose_can_draw_layers_under_and_over_the_base():
    data = compose_data(loop=False)
    data["animations"]["watch"]["compose"].update({"over": "cat", "over_at": [1, 2]})
    a = load_manifest(data, {1: (20, 10), 2: (30, 10)}, bbox_all)["watch"]
    f = a.frames[0]
    assert f.under[0][2] == (60, -44) and f.over[0][2] == (1, 2)


def test_one_shot_compose_can_follow_the_layer_drawn_over():
    data = compose_data(loop=False)
    data["animations"]["watch"]["compose"] = {"base": "cat", "under": "cat", "over": "tv", "length": "over"}
    a = load_manifest(data, {1: (20, 10), 2: (30, 10)}, bbox_all)["watch"]
    assert len(a.frames) == 6  # la télé : 3 images à 3 i/s, soit 6 images à 6 i/s


def test_frame_bounds_include_the_layers_drawn_over():
    from felix.core.anim import Frame, frame_bounds
    f = Frame(1, (0, 0, 10, 10), (5, 9), over=((2, (0, 0, 4, 4), (8, 9)),))
    assert frame_bounds(f) == (0, 0, 12, 13)


def test_compose_can_follow_the_base_length_and_shift_at_the_end():
    data = compose_data(loop=False)
    data["animations"]["watch"]["compose"]["length"] = "base"
    data["animations"]["watch"]["exit"] = [9, 9]
    a = load_manifest(data, {1: (20, 10), 2: (30, 10)}, bbox_all)["watch"]
    assert len(a.frames) == 2  # la durée du chat, la télé suit
    assert a.shift == (4, 0)  # sortie 9 − ancre 5


def test_extensions_are_merged_into_the_manifest():
    from felix.core.manifest import merge_manifests
    base = {"sheets": {"1": [2, 1]}, "erase": {"1": [[0, 0, 1, 1]]},
            "animations": {"cat": {"sheet": 1, "frames": "0-1"}}}
    fun = {"sheets": {"500": [1, 1]},
           "animations": {"mouse": {"sheet": 500, "frames": "0"},
                          "play": {"compose": {"base": "cat", "over": "mouse"}}}}
    merged = merge_manifests(base, [fun])
    assert set(merged["sheets"]) == {"1", "500"} and merged["erase"] == base["erase"]
    assert set(merged["animations"]) == {"cat", "mouse", "play"}
    assert set(base["animations"]) == {"cat"}  # la base n'est pas modifiée
    anims = load_manifest(merged, {1: (20, 10), 500: (5, 5)}, bbox_all)
    assert anims["play"].frames[0].over[0][0] == 500


def test_an_extension_cannot_redefine_what_exists():
    import pytest
    from felix.core.manifest import merge_manifests
    base = {"sheets": {"1": [2, 1]}, "animations": {"cat": {"sheet": 1, "frames": "0-1"}}}
    with pytest.raises(ValueError, match="cat"):
        merge_manifests(base, [{"animations": {"cat": {"sheet": 1, "frames": "0"}}}])
