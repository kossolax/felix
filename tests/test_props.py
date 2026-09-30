from PySide6.QtGui import QColor, QImage

from felix.render.props import PropManager


class FakeBank:
    def __init__(self):
        img = QImage(40, 40, QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255, 255))
        self.sheets = {122: img}


def test_marks_event_shows_one_prop_per_mark(qapp):
    props = PropManager(FakeBank(), lifetime=60)
    props.handle(("marks", [((122, 2, 3, 9, 12), (500, 900)), ((122, 20, 3, 10, 11), (540, 905))]))
    geoms = sorted((w.x(), w.y(), w.width(), w.height()) for w in props.windows)
    assert geoms == [(500, 900, 9, 12), (540, 905, 10, 11)]


def test_claws_event_draws_marks_between_top_and_bottom(qapp):
    props = PropManager(FakeBank(), lifetime=60)
    props.handle(("claws", 700.0, 400, 800))
    (w,) = props.windows
    assert w.y() == 400 and w.height() == 400 and w.x() < 700 < w.x() + w.width()


def test_old_props_are_dropped_beyond_the_limit(qapp):
    props = PropManager(FakeBank(), lifetime=60, limit=3)
    for i in range(5):
        props.handle(("claws", 100.0 * i, 400, 500))
    assert len(props.windows) == 3


def test_sounds_are_not_props(qapp):
    props = PropManager(FakeBank(), lifetime=60)
    props.handle("meow")
    assert props.windows == []
