"""HUD / tray / settings-window tests (offscreen Qt, PLAN.md §1.3, §3, §5).

These prove the display-only construction: the pill and ring cannot
steal focus or clicks, and the windows carry the right state tokens.
Requires PyQt6 (installed in the test venv). Written against the real
hud.py/tray.py API (TOKENS, set_hold(pos, progress), _sliders, ...).
"""

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt

from touchless.hud import (
    TOKENS, CalibrationWindow, FirstRunWizard, HudPill, PreviewPane,
    RingWindow, SettingsWindow, SoundPlayer, SOUND_FREQUENCIES,
)
from touchless.settings import Settings
from touchless.state import State
from touchless.tray import FakeTrayBackend, TrayController


def test_tokens_cover_every_state():
    for state in State:
        assert state.value in TOKENS
        assert TOKENS[state.value].startswith("#")


def test_pill_display_only_flags(qapp):
    pill = HudPill(Settings())
    flags = pill.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool
    assert pill.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert pill.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    pill.set_state("TRACKING", "Point", 0.5)
    assert pill.state == "TRACKING"
    assert pill.chip == "Point"
    assert pill.hold_progress == 0.5
    pill.set_state("PAUSED", transient="Hello")
    assert pill.transient == "Hello"
    pill.clear_transient()
    assert pill.transient is None


def test_ring_window_progress_and_clear(qapp):
    ring = RingWindow()
    ring.set_hold((1200, 800), 0.5)
    assert ring.progress == 0.5 and ring.cursor_pos == (1200, 800)
    ring.set_hold(None, None)
    assert ring.progress is None and ring.cursor_pos is None


def test_preview_pane_accepts_frame(qapp):
    import numpy as np
    from conftest import open_palm_landmarks
    pane = PreviewPane()
    pane.update_frame(np.zeros((480, 640, 3), dtype=np.uint8),
                      [open_palm_landmarks()], 1)
    assert pane._extra_hands == 1


def test_tray_controller_mirrors_state(qapp):
    tray_backend = FakeTrayBackend()
    controller = TrayController(tray_backend)
    controller.set_state("TRACKING")
    assert tray_backend.icons == ["TRACKING"]
    assert "Tracking" in tray_backend.tooltips[-1]
    assert tray_backend.pause_labels == [False]
    controller.set_state("PAUSED")
    assert tray_backend.pause_labels[-1] is True
    controller.set_state("ERROR")
    assert "Error" in tray_backend.tooltips[-1]


def test_calibration_window_signals(qapp):
    window = CalibrationWindow()
    window.set_targets([(192, 108), (1728, 108), (192, 972), (1728, 972), (960, 540)],
                       0, [])
    fired = []
    window.redo_requested.connect(lambda i: fired.append(("redo", i)))
    window.skip_requested.connect(lambda: fired.append(("skip",)))
    window.cancel_requested.connect(lambda: fired.append(("cancel",)))
    window._redo.click()
    window._skip.click()
    window._cancel.click()
    assert ("redo", 0) in fired and ("skip",) in fired and ("cancel",) in fired


def test_settings_window_reset_and_scaled_reconcile(qapp):
    settings = Settings()
    settings.save = lambda path=None: None  # never touch the real home dir
    settings.sensitivity = 2.0
    settings.hold_time_ms = 1200
    window = SettingsWindow(settings, [0, 1])
    # Reset must restore ALL defaults, including the scaled sliders
    # (sensitivity/hud_scale/hud_opacity are reconciled in accept()).
    window._on_reset()
    assert settings.sensitivity == 1.0
    assert settings.hold_time_ms == 600
    assert settings.pause_key == "F9"
    assert settings.hud_scale == 1.0
    # Scaled sliders reconcile to floats in accept(), never stored raw.
    window2 = SettingsWindow(settings, [0, 1])
    window2._sliders["sensitivity_x10"].setValue(20)
    window2.accept()
    assert settings.sensitivity == 2.0


def test_sound_frequencies_distinct():
    freqs = [freq for freq, _dur in SOUND_FREQUENCIES.values()]
    assert len(set(freqs)) == len(freqs)  # every signal sounds different
    assert "activation" in SOUND_FREQUENCIES and "error" in SOUND_FREQUENCIES
    player = SoundPlayer(enabled=False)
    player.play("unknown_event")  # unknown names are silent, never crash
    assert player.played == ["unknown_event"]


def test_first_run_wizard_pages(qapp):
    wizard = FirstRunWizard()
    assert wizard._stack.count() >= 8
    assert wizard.current_step() == "welcome"
