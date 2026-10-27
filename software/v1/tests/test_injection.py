"""Injection tests — PLAN.md §9, §4 E10, §2 J6."""

import pytest

from touchless.injection import (
    E10_MESSAGE, FakeBackend, InjectionBlocked, Injector,
)
from conftest import FakeElevation


def test_passthrough_records_calls():
    backend = FakeBackend()
    injector = Injector(backend, FakeElevation(False))
    injector.move(100, 200)
    injector.click()
    injector.mouse_down()
    injector.scroll(3)
    injector.mouse_up()
    kinds = [c[0] for c in backend.calls]
    assert kinds == ["move", "click", "mouse_down", "scroll", "mouse_up"]
    assert backend.screen_size() == (1920, 1080)


def test_elevated_target_blocks_moves_clicks_scrolls():
    backend = FakeBackend()
    injector = Injector(backend, FakeElevation(True))
    for fn in (lambda: injector.move(1, 2), injector.click,
               lambda: injector.scroll(1), injector.mouse_down):
        with pytest.raises(InjectionBlocked) as excinfo:
            fn()
        assert excinfo.value.message == E10_MESSAGE
    assert backend.calls == []  # nothing reached the backend


def test_button_up_is_never_blocked():
    """J6: releasing a held button must work even for elevated targets."""
    backend = FakeBackend()
    injector = Injector(backend, FakeElevation(True))
    backend.button_held = True
    injector.mouse_up()
    assert ("mouse_up",) in backend.calls
    assert backend.button_held is False


def test_release_all_is_unconditional():
    backend = FakeBackend()
    injector = Injector(backend, FakeElevation(True))
    backend.button_held = True
    injector.release_all()  # must not raise, must release
    assert backend.button_held is False
