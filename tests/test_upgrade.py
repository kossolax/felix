from felix.platform.detect import BackendUpgrader


class Dummy:
    def __init__(self, name):
        self.name = name
        self.stopped = False

    def stop(self):
        self.stopped = True


def test_upgrade_happens_once_the_helper_shows_up():
    available = {"now": False}
    upgrader = BackendUpgrader(check=lambda: available["now"], factory=lambda: Dummy("gnome_shell"))
    current = Dummy("degraded")
    assert upgrader.poll(current) is None
    available["now"] = True
    new = upgrader.poll(current)
    assert new.name == "gnome_shell" and current.stopped
    assert upgrader.poll(new) is None  # plus rien à faire ensuite


def test_failed_factory_keeps_the_current_backend():
    def broken():
        raise RuntimeError("D-Bus indisponible")

    upgrader = BackendUpgrader(check=lambda: True, factory=broken)
    current = Dummy("degraded")
    assert upgrader.poll(current) is None
    assert not current.stopped
