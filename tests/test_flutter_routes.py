
import pytest

from cidd.engine.bootstrap import (
    BootstrapError,
    _screen_route,
)


@pytest.mark.parametrize(
    "screen, expected",
    [
        ("SplashScreen", "/splash"),
        ("TodoView", "/todo"),
        ("AboutView", "/about"),
        ("DriverDashboardView", "/driver-dashboard"),
        ("PassengerHomeScreen", "/passenger-home"),
    ],
)
def test_screen_route(screen, expected):
    assert _screen_route(screen) == expected


@pytest.mark.parametrize(
    "screen",
    [
        "",
        "badScreen",
        "../AboutView",
        "About View",
    ],
)
def test_invalid_screen_route(screen):
    with pytest.raises(BootstrapError):
        _screen_route(screen)
