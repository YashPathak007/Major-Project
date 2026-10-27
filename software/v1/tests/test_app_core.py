"""AppCore tests — PLAN.md §2 journeys, §4 E1–E14, §7 gates G-GATE/G-DRAG.

Every test drives AppCore._iterate() directly with scripted cameras
and landmarkers (no threads, no display, no Windows box) except the
explicit lifecycle tests, which start + shut down the real threads.
"""

import os
import subprocess
import sys
import time
from collections import deque

import pytest

from touchless.app import AppCore, ERROR_TEXT
from touchless.camera import Camera, FakeCapture
from touchless.gestures import HandFrame
from touchless.injection import E10_MESSAGE, FakeBackend, Injector
from touchless.logging import EventLogger
from touchless.model import FakeLandmarker, ModelMissingError, HandResult
from touchless.settings import Settings
from touchless.state import State
from conftest import (
    FakeClock, FakeElevation, bright_frame, dark_frame, fist_landmarks,
    hand_result, idle_landmarks, make_core, open_palm_landmarks,
    pinch_landmarks, shift_landmarks,
)


def run_frames(core, clock, n, step=1 / 30.0):
    for _ in range(n):
        core._iterate()
        clock.advance(step)


def to_tracking(core, clock):
    """PAUSED -> TRACKING via the G0 open-palm gate."""
    run_frames(core, clock, 8, step=0.1)
    assert core.state.state is State.TRACKING


def test_gate_activation_to_tracking(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    assert core.state.state is State.PAUSED
    run_frames(core, clock, 3, step=0.1)
    assert core.state.state is State.PAUSED  # gate needs a brief hold
    run_frames(core, clock, 4, step=0.1)
    assert core.state.state is State.TRACKING
    sounds = [e.sound for e in core.drain_events()]
    assert "activation" in sounds
    assert core.logger.count("activation") == 1


def test_click_and_hold_click_paths(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    to_tracking(core, clock)
    # Quick pinch -> click on release.
    core.landmarker.script = [[hand_result(pinch_landmarks())]]
    run_frames(core, clock, 3)
    core.landmarker.script = [[hand_result(idle_landmarks())]]
    run_frames(core, clock, 3)
    assert ("click",) in core.backend.calls
    # Hold pinch past the ring -> hold-click, no quick click after.
    core.backend.calls.clear()
    core.landmarker.script = [[hand_result(pinch_landmarks())]]
    run_frames(core, clock, 3)
    clock.advance(0.7)
    run_frames(core, clock, 3)
    assert ("click",) in core.backend.calls  # the hold-click fired
    core.backend.calls.clear()
    core.landmarker.script = [[hand_result(idle_landmarks())]]
    run_frames(core, clock, 3)
    assert ("click",) not in core.backend.calls


def test_drag_start_end_and_hand_lost_cancels(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    to_tracking(core, clock)
    core.backend.calls.clear()
    # Pinch, then move the whole hand -> drag starts.
    core.landmarker.script = [[hand_result(pinch_landmarks())]]
    run_frames(core, clock, 3)
    moved = shift_landmarks(pinch_landmarks(), 0.08, 0.0)
    core.landmarker.script = [[hand_result(moved)]]
    run_frames(core, clock, 3)
    assert ("mouse_down",) in core.backend.calls
    # Hand lost mid-drag -> button released, HAND_LOST, no stuck drag.
    core.landmarker.script = [[]]
    run_frames(core, clock, 2)
    assert core.state.state is State.HAND_LOST
    assert ("mouse_up",) in core.backend.calls
    assert core.backend.button_held is False
    # Hand returns -> auto-resume to TRACKING without re-clicking.
    core.landmarker.script = [[hand_result(open_palm_landmarks())]]
    run_frames(core, clock, 2)
    assert core.state.state is State.TRACKING


def test_scroll_open_palm_vertical(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    to_tracking(core, clock)
    core.backend.calls.clear()
    moved = shift_landmarks(open_palm_landmarks(), 0.0, -0.12)
    core.landmarker.script = [[hand_result(moved)]]
    run_frames(core, clock, 3, step=0.1)
    scrolls = [c for c in core.backend.calls if c[0] == "scroll"]
    assert scrolls and scrolls[0][1] > 0  # hand up -> scroll up


def test_second_hand_ignored_e6(tmp_path):
    clock = FakeClock()
    primary = hand_result(open_palm_landmarks(), "Right", area=0.05)
    second = hand_result(open_palm_landmarks(), "Left", area=0.04)
    core = make_core(tmp_path, landmarker_script=[[primary, second]], clock=clock)
    to_tracking(core, clock)
    assert core.state.state is State.TRACKING
    run_frames(core, clock, 3)
    assert core.state.state is State.TRACKING  # no mode change (E6)
    assert core.snapshot()["extra_hands"] == 1


def test_gate_closed_zero_injections_e13_ggate(tmp_path):
    """G-GATE (release-blocking): nothing injects while PAUSED."""
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(pinch_landmarks())]],
                     clock=clock)
    assert core.state.state is State.PAUSED
    run_frames(core, clock, 4)  # pinch held while paused: must not click
    core.landmarker.script = [[hand_result(idle_landmarks())]]
    run_frames(core, clock, 3)  # release while paused: must not click
    core.landmarker.script = [[hand_result(fist_landmarks())]]
    run_frames(core, clock, 3)  # fist while paused: must not pause-loop
    assert core.backend.calls == []
    # Defense in depth: a direct inject attempt while paused is refused.
    assert core._safe_inject(core.injector.click) is False
    assert core.logger.count("false_trigger") == 1


def test_elevated_target_e10(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock, elevation=FakeElevation(True))
    to_tracking(core, clock)
    core.backend.calls.clear()
    core.landmarker.script = [[hand_result(pinch_landmarks())]]
    run_frames(core, clock, 3)
    core.landmarker.script = [[hand_result(idle_landmarks())]]
    run_frames(core, clock, 3)
    assert ("click",) not in core.backend.calls  # blocked, not silent
    assert core.snapshot()["transient"] == E10_MESSAGE
    assert core.state.state is State.TRACKING  # still works elsewhere


def test_low_light_degraded_and_recovery_e7(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     frames=[dark_frame()], clock=clock)
    to_tracking(core, clock)
    run_frames(core, clock, 35)  # fill the brightness window with dark
    clock.advance(6.0)
    run_frames(core, clock, 2)
    assert core.state.state is State.DEGRADED
    assert "Light is low" in (core.snapshot()["transient"] or "")
    core.camera.backend.frames = [bright_frame()]
    run_frames(core, clock, 35)
    clock.advance(6.0)
    run_frames(core, clock, 2)
    assert core.state.state is State.TRACKING


def test_low_fps_steps_down_then_degrades_e8(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    to_tracking(core, clock)
    # Fake a slow camera: 30 frame times spanning 60 s -> ~0.5 fps.
    core.camera._frame_times = deque([1000.0 + i * 2.0 for i in range(30)], maxlen=30)
    for _ in range(3):
        clock.advance(6.0)
        core._evaluate_degradation(clock.now)
    assert core.state.state is State.DEGRADED
    assert core.camera.width == 320  # ladder walked to the bottom first


def test_no_hand_guidance_e4(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[]], clock=clock)
    assert core.state.state is State.PAUSED
    run_frames(core, clock, 2)
    assert core.snapshot()["transient"] is None
    clock.advance(11.0)
    run_frames(core, clock, 2)
    assert "No hand found yet" in (core.snapshot()["transient"] or "")


def test_start_failures_e1_e2_e3_e9(tmp_path):
    def build_core(camera, factory):
        settings = Settings()
        logger = EventLogger(directory=tmp_path / "logs", enabled=True)
        backend = FakeBackend()
        return AppCore(settings, logger, camera, factory,
                       Injector(backend, FakeElevation(False)), clock=FakeClock())

    # E1: no devices at all.
    camera = Camera(FakeCapture(open_fails=True),
                    probe_factory=lambda: FakeCapture(open_fails=True))
    core = build_core(camera, lambda p: FakeLandmarker([]))
    assert core.start() is False
    assert core.state.state is State.ERROR and core.state.error_id == "E1"
    assert core.state.error_message == ERROR_TEXT["E1"][0]

    # E2: permission denied.
    camera = Camera(FakeCapture(permission_error=True))
    core = build_core(camera, lambda p: FakeLandmarker([]))
    assert core.start() is False
    assert core.state.error_id == "E2"
    assert "Let desktop apps access your camera" in core.state.error_message

    # E3: devices exist but the camera is busy.
    camera = Camera(FakeCapture(open_fails=True))
    core = build_core(camera, lambda p: FakeLandmarker([]))
    assert core.start() is False
    assert core.state.error_id == "E3"

    # E9: camera fine, model file missing.
    def raising_factory(path):
        raise ModelMissingError("no model")
    camera = Camera(FakeCapture(frames=[bright_frame()]))
    core = build_core(camera, raising_factory)
    assert core.start() is False
    assert core.state.error_id == "E9"
    assert "Expected location" in core.state.error_message

    # Retry from ERROR: fix the camera -> PAUSED (never straight to TRACKING).
    camera.backend = FakeCapture(frames=[bright_frame()])
    assert core.retry_from_error() is False  # model still missing -> stays E9
    core.landmarker_factory = lambda p: FakeLandmarker([])
    assert core.retry_from_error() is True
    assert core.state.state is State.PAUSED


def test_quit_during_drag_releases_button_gdrag(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    to_tracking(core, clock)
    core.landmarker.script = [[hand_result(pinch_landmarks())]]
    run_frames(core, clock, 3)
    moved = shift_landmarks(pinch_landmarks(), 0.08, 0.0)
    core.landmarker.script = [[hand_result(moved)]]
    run_frames(core, clock, 3)
    assert core.backend.button_held is True
    core.shutdown()
    assert core.backend.button_held is False
    assert ("mouse_up",) in core.backend.calls
    assert core.camera.backend.released is True
    assert core.state.state is State.OFF


def test_pause_resume_and_hotkeys(tmp_path):
    from touchless.app import FakeHotkeys
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    hotkeys = FakeHotkeys(core._toggle_pause, core.shutdown)
    to_tracking(core, clock)
    hotkeys.press_pause()
    assert core.state.state is State.PAUSED
    hotkeys.press_pause()  # deliberate key resume (documented)
    assert core.state.state is State.TRACKING
    hotkeys.press_quit()
    assert core.state.state is State.OFF


def test_calibration_capture_redo_skip_cancel(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    core.start_calibration()
    assert core.state.state is State.CALIBRATING
    snap = core.snapshot()["calibration"]
    assert snap is not None and len(snap["targets"]) == 5

    # Capture one point, redo it, then cancel: profile untouched.
    core.landmarker.script = [[hand_result(pinch_landmarks())]]
    run_frames(core, clock, 3)
    clock.advance(0.7)
    run_frames(core, clock, 3)
    assert len(core.calibration.captured) == 1
    core.calibration_redo(0)
    assert len(core.calibration.captured) == 0
    core.calibration_cancel()
    assert core.state.state is State.PAUSED
    assert core.settings.active_profile_obj.points.top_left is None

    # Skip: defaults for this session, stored profile untouched.
    core.start_calibration()
    core.calibration_skip()
    assert core.state.state is State.PAUSED
    x, y = core.mapper.calibration(0.05, 0.05)
    assert x == 0.0 and y == 0.0  # default map active


def test_calibration_full_run_recovers_mapping(tmp_path):
    """5 captures from a known affine map must recover that map.

    Captured points are stored in mirrored hand space (the mapper
    mirrors before fitting), so assertions use mirrored coordinates.
    Each capture is separated by a release, because a pinch session
    is consumed once its ring completes.
    """
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    core.start_calibration()
    targets = list(core.calibration.targets)
    # Truth: screen = 1700*hx + 80, 1000*hy + 40 (all hand points in
    # [0, 1] for the 10%-inset targets on a 1920x1080 screen).
    raw_points = []
    for tx, ty in targets:
        hx = (tx - 80) / 1700.0
        hy = (ty - 40) / 1000.0
        raw_points.append((hx, hy))
        hand = shift_landmarks(pinch_landmarks(), hx - 0.42, hy - 0.60)
        core.landmarker.script = [[hand_result(idle_landmarks())]]
        run_frames(core, clock, 2)  # release: reset the pinch session
        core.landmarker.script = [[hand_result(hand)]]
        run_frames(core, clock, 3)
        clock.advance(0.7)
        run_frames(core, clock, 3)
    assert core.state.state is State.PAUSED
    assert core.calibration is None
    profile = core.settings.active_profile_obj
    stored = [profile.points.top_left, profile.points.top_right,
              profile.points.bottom_left, profile.points.bottom_right,
              profile.points.centre]
    assert all(p is not None for p in stored)
    for (hx, hy), (tx, ty), stored_pt in zip(raw_points, targets, stored):
        # Stored points are mirrored: (1 - hx, hy).
        assert abs(stored_pt[0] - (1.0 - hx)) < 1e-6
        assert abs(stored_pt[1] - hy) < 1e-6
        gx, gy = core.mapper.calibration(stored_pt[0], stored_pt[1])
        assert abs(gx - tx) < 5.0 and abs(gy - ty) < 5.0


def test_wizard_driver_steps_and_tasks(tmp_path):
    from touchless.app import WizardDriver
    driver = WizardDriver()
    assert driver.step == "welcome"
    driver.advance()
    assert driver.step == "camera"
    while driver.step != "task_move":
        driver.advance()
    driver.on_cursor((0, 0))
    driver.on_cursor((200, 0))
    assert "task_move" in driver.done
    driver.advance()
    assert driver.step == "task_click"
    driver.on_click()
    assert "task_click" in driver.done


def test_lifecycle_start_and_clean_shutdown(tmp_path):
    clock = FakeClock()
    core = make_core(tmp_path, landmarker_script=[[hand_result(open_palm_landmarks())]],
                     clock=clock)
    # make_core leaves the core in PAUSED without threads; start the
    # real lifecycle on a fresh core and shut it down cleanly.
    settings = Settings()
    logger = EventLogger(directory=tmp_path / "logs", enabled=True)
    camera = Camera(FakeCapture(frames=[bright_frame()]))
    backend = FakeBackend()
    fresh = AppCore(settings, logger, camera, lambda p: FakeLandmarker([]),
                    Injector(backend, FakeElevation(False)), clock=clock)
    try:
        assert fresh.start() is True
        assert fresh.state.state is State.PAUSED
        time.sleep(0.2)
    finally:
        fresh.shutdown()
    assert fresh.state.state is State.OFF
    assert camera.backend.released is True


def test_hung_pipeline_quit_still_exits_process(tmp_path):
    """J6 watchdog: tray Quit must kill the process even if inference hangs."""
    import shutil
    from pathlib import Path
    shutil.copy(Path(__file__).resolve().parent / "hang_quit_probe.py",
                tmp_path / "probe.py")
    src = str(Path(__file__).resolve().parent.parent / "src")
    env = dict(os.environ, TOUCHLESS_SRC=src)
    proc = subprocess.run([sys.executable, str(tmp_path / "probe.py")],
                          capture_output=True, text=True, timeout=20,
                          cwd=str(tmp_path), env=env)
    assert proc.returncode == 0, f"probe failed: {proc.stdout} {proc.stderr}"
