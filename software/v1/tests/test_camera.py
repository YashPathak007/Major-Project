"""Camera tests — PLAN.md §9 diagnostics (E1/E2/E3), resolution ladder."""

from touchless.camera import (
    BLACK_FRAME_STREAK, Camera, Diagnosis, FakeCapture, frame_brightness,
)
from conftest import bright_frame, dark_frame


def test_bright_frame_read_and_brightness():
    camera = Camera(FakeCapture(frames=[bright_frame()]))
    assert camera.open(0)
    ok, frame, brightness = camera.read()
    assert ok and frame is not None
    assert brightness > 150.0
    assert frame_brightness(dark_frame()) < 20.0


def test_open_failure_with_devices_is_busy():
    camera = Camera(FakeCapture(open_fails=True))
    assert not camera.open(0)
    # The probe factory uses a working backend, so devices ARE present.
    assert camera.diagnose() == Diagnosis.BUSY


def test_no_devices_is_absent():
    camera = Camera(FakeCapture(open_fails=True),
                    probe_factory=lambda: FakeCapture(open_fails=True))
    assert camera.diagnose() == Diagnosis.ABSENT


def test_permission_error_is_permission():
    camera = Camera(FakeCapture(permission_error=True))
    assert camera.diagnose() == Diagnosis.PERMISSION


def test_sustained_black_frames_diagnosis():
    camera = Camera(FakeCapture(frames=[dark_frame()]))
    assert camera.open(0)
    for _ in range(BLACK_FRAME_STREAK + 1):
        camera.read()
    assert camera.black_frames_sustained
    assert camera.diagnose() == Diagnosis.BLACK_FRAMES


def test_resolution_ladder_steps_down_then_stops():
    camera = Camera(FakeCapture(frames=[bright_frame()]))
    assert camera.open(0)
    assert (camera.width, camera.height) == (1280, 720)
    assert camera.step_down_resolution()
    assert (camera.width, camera.height) == (640, 480)
    assert camera.step_down_resolution()
    assert (camera.width, camera.height) == (320, 240)
    assert not camera.step_down_resolution()  # already lowest


def test_fps_computed_from_frame_times():
    import time
    camera = Camera(FakeCapture(frames=[bright_frame()]))
    assert camera.open(0)
    for _ in range(5):
        camera.read()
        time.sleep(0.01)
    assert camera.fps > 0
