import pytest

from felix.platform.detect import choose_backend, prepare_environment


def test_windows_session():
    env = {}
    assert prepare_environment(env, "win32") == "windows"
    assert "QT_QPA_PLATFORM" not in env


@pytest.mark.parametrize("env", [{"WAYLAND_DISPLAY": "wayland-0"}, {"XDG_SESSION_TYPE": "wayland"}])
def test_wayland_session_forces_xwayland(env):
    assert prepare_environment(env, "linux") == "wayland"
    assert env["QT_QPA_PLATFORM"] == "xcb"


def test_explicit_qt_platform_is_kept():
    env = {"WAYLAND_DISPLAY": "wayland-0", "QT_QPA_PLATFORM": "offscreen"}
    prepare_environment(env, "linux")
    assert env["QT_QPA_PLATFORM"] == "offscreen"


def test_x11_session():
    env = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}
    assert prepare_environment(env, "linux") == "x11"
    assert "QT_QPA_PLATFORM" not in env


@pytest.mark.parametrize("session, helper, expected", [
    ("windows", False, "windows"),
    ("x11", False, "x11"),
    ("x11", True, "gnome_shell"),
    ("wayland", True, "gnome_shell"),
    ("wayland", False, "degraded"),
])
def test_choose_backend(session, helper, expected):
    assert choose_backend(session, "auto", helper) == expected


def test_requested_backend_wins():
    assert choose_backend("x11", "degraded", True) == "degraded"
