"""Backend factice alimenté par une scène JSON (tests, --probe)."""
import json
from pathlib import Path

from felix.core.world import Monitor, Rect, WinRect, WorldSnapshot


def scene_from_dict(data):
    return WorldSnapshot(
        monitors=tuple(Monitor(Rect(*m["geometry"]), Rect(*m.get("workarea", m["geometry"])))
                       for m in data.get("monitors", [])),
        windows=tuple(WinRect(w["id"], Rect(*w["rect"]), w.get("fullscreen", False))
                      for w in data.get("windows", [])),
        cursor=tuple(data["cursor"]) if data.get("cursor") else None,
    )


def scene_to_dict(snap):
    def r(rect):
        return [rect.x, rect.y, rect.w, rect.h]
    return {
        "monitors": [{"geometry": r(m.geometry), "workarea": r(m.workarea)} for m in snap.monitors],
        "windows": [{"id": w.id, "rect": r(w.rect), "fullscreen": w.fullscreen} for w in snap.windows],
        "cursor": list(snap.cursor) if snap.cursor else None,
    }


def load_scene(path):
    return scene_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


class FakeBackend:
    name = "fake"

    def __init__(self, snap):
        self._snap = snap

    def set(self, snap):
        self._snap = snap

    def snapshot(self):
        return self._snap

    def stop(self):
        pass
