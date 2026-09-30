import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows uniquement")


def test_windows_backend_reads_monitors_and_windows(qapp):
    from felix.platform.windows import WindowsBackend, monitors, window_infos
    assert monitors(), "au moins un écran"
    assert isinstance(window_infos(), list)
    backend = WindowsBackend(interval=0.05)
    try:
        assert backend.wait_ready(3)
        snap = backend.snapshot()
        assert snap.monitors and snap.cursor is not None
        for m in snap.monitors:
            assert m.workarea.w > 0 and m.workarea.h > 0
    finally:
        backend.stop()
