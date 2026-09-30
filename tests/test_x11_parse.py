from felix.core.world import Rect
from felix.platform.x11_parse import ALL_DESKTOPS, frame_rect, is_candidate, workareas_for


def test_frame_rect_adds_server_side_decorations():
    # client à (100, 130), 400×300, barre de titre 30 px
    assert frame_rect(100, 130, 400, 300, net_extents=(0, 0, 30, 0), gtk_extents=None) == Rect(100, 100, 400, 330)


def test_frame_rect_removes_client_side_shadows():
    # fenêtre GTK CSD avec 20 px d'ombre de chaque côté (26 en bas)
    assert frame_rect(80, 80, 440, 346, net_extents=None, gtk_extents=(20, 20, 20, 26)) == Rect(100, 100, 400, 300)


def test_frame_rect_without_extents_is_the_client():
    assert frame_rect(5, 6, 7, 8, None, None) == Rect(5, 6, 7, 8)


def test_candidate_windows():
    assert is_candidate(["_NET_WM_WINDOW_TYPE_NORMAL"], [], 0, 0)
    assert is_candidate([], [], 0, 0)  # pas de type = normale
    assert is_candidate(["_NET_WM_WINDOW_TYPE_DIALOG"], [], ALL_DESKTOPS, 1)
    assert not is_candidate(["_NET_WM_WINDOW_TYPE_DESKTOP"], [], 0, 0)
    assert not is_candidate(["_NET_WM_WINDOW_TYPE_DOCK"], [], 0, 0)
    assert not is_candidate(["_NET_WM_WINDOW_TYPE_NORMAL"], ["_NET_WM_STATE_HIDDEN"], 0, 0)
    assert not is_candidate(["_NET_WM_WINDOW_TYPE_NORMAL"], [], 1, 0)


def test_workareas_match_monitors_and_fall_back_to_geometry():
    monitors = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1280, 1024)]
    values = [0, 32, 1920, 1048]  # une seule zone : l'autre écran garde sa géométrie
    assert workareas_for(values, monitors) == [Rect(0, 32, 1920, 1048), Rect(1920, 0, 1280, 1024)]


def test_single_net_workarea_is_clipped_to_each_monitor():
    monitors = [Rect(0, 0, 1920, 1080), Rect(1920, 0, 1280, 1024)]
    union = [0, 32, 3200, 992]  # _NET_WORKAREA couvre les deux écrans
    assert workareas_for(union, monitors) == [Rect(0, 32, 1920, 992), Rect(1920, 32, 1280, 992)]
