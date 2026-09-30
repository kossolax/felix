from felix.platform.degraded import QtScreensBackend


def test_snapshot_lists_qt_screens_without_windows(qapp):
    snap = QtScreensBackend(cursor=False).snapshot()
    assert len(snap.monitors) == len(qapp.screens()) >= 1
    g = qapp.screens()[0].geometry()
    assert (snap.monitors[0].geometry.w, snap.monitors[0].geometry.h) == (g.width(), g.height())
    assert snap.windows == () and snap.cursor is None


def test_cursor_is_reported_when_enabled(qapp):
    assert QtScreensBackend(cursor=True).snapshot().cursor is not None
