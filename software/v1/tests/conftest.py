"""Shared fixtures for the Touchless V1 test suite.

All tests are synthetic/headless: no camera, no display, no Windows
box. Qt tests run offscreen. Landmark fixtures are hand-built
21-point hands (not recordings of any real person).
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from touchless.app import AppCore  # noqa: E402
from touchless.camera import Camera, FakeCapture  # noqa: E402
from touchless.gestures import HandFrame  # noqa: E402
from touchless.injection import FakeBackend, Injector  # noqa: E402
from touchless.logging import EventLogger  # noqa: E402
from touchless.model import FakeLandmarker, HandResult  # noqa: E402
from touchless.settings import Settings  # noqa: E402
from touchless.state import State  # noqa: E402


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _hand(points: dict) -> list:
    """Build a 21-landmark hand from an index -> (x, y) map."""
    base = {i: (0.5, 0.5, 0.0) for i in range(21)}
    for idx, (x, y) in points.items():
        base[idx] = (x, y, 0.0)
    return [base[i] for i in range(21)]


def open_palm_landmarks() -> list:
    return _hand({
        0: (0.50, 0.90),
        1: (0.42, 0.82), 2: (0.38, 0.78), 3: (0.30, 0.70), 4: (0.22, 0.62),
        5: (0.44, 0.68), 6: (0.44, 0.52), 7: (0.44, 0.40), 8: (0.44, 0.28),
        9: (0.50, 0.66), 10: (0.50, 0.50), 11: (0.50, 0.38), 12: (0.50, 0.26),
        13: (0.56, 0.68), 14: (0.56, 0.52), 15: (0.56, 0.40), 16: (0.56, 0.28),
        17: (0.62, 0.70), 18: (0.62, 0.56), 19: (0.62, 0.46), 20: (0.62, 0.36),
    })


def fist_landmarks() -> list:
    return _hand({
        0: (0.50, 0.90),
        1: (0.44, 0.84), 2: (0.40, 0.80), 3: (0.44, 0.82), 4: (0.47, 0.84),
        5: (0.44, 0.68), 6: (0.44, 0.54), 7: (0.45, 0.62), 8: (0.46, 0.72),
        9: (0.50, 0.66), 10: (0.50, 0.52), 11: (0.51, 0.60), 12: (0.52, 0.70),
        13: (0.56, 0.68), 14: (0.56, 0.54), 15: (0.57, 0.62), 16: (0.58, 0.72),
        17: (0.62, 0.70), 18: (0.62, 0.58), 19: (0.63, 0.64), 20: (0.64, 0.72),
    })


def pinch_landmarks() -> list:
    pts = open_palm_landmarks()
    pts[2] = (0.38, 0.78, 0.0)
    pts[3] = (0.38, 0.70, 0.0)
    pts[4] = (0.40, 0.60, 0.0)  # thumb tip meets index tip
    pts[6] = (0.44, 0.54, 0.0)
    pts[7] = (0.43, 0.50, 0.0)
    pts[8] = (0.42, 0.60, 0.0)  # index tip curled to the thumb
    return pts


def idle_landmarks() -> list:
    """A relaxed hand: no gate pose, no pinch, no fist (POSE_NONE)."""
    pts = open_palm_landmarks()
    pts[3] = (0.32, 0.70, 0.0)
    pts[4] = (0.30, 0.75, 0.0)  # thumb folded back, tips far apart
    return pts


def shift_landmarks(landmarks: list, dx: float, dy: float) -> list:
    return [(x + dx, y + dy, z) for x, y, z in landmarks]


def hand_result(landmarks, handedness="Right", area=0.05) -> HandResult:
    return HandResult(landmarks=landmarks, handedness=handedness, area=area)


def bright_frame():
    return np.full((480, 640, 3), 200, dtype=np.uint8)


def dark_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


class FakeElevation:
    def __init__(self, elevated: bool = False):
        self.elevated = elevated

    def is_foreground_elevated(self) -> bool:
        return self.elevated


def make_core(tmp_path, landmarker_script=None, frames=None, clock=None,
              elevation=None, settings=None):
    """Build an AppCore wired to fakes, sitting in PAUSED (no threads).

    The pipeline thread is NOT started: tests drive _iterate()
    directly so every step is deterministic.
    """
    clock = clock or FakeClock()
    settings = settings or Settings()
    orig_save = settings.save
    settings.save = lambda p=None: orig_save(tmp_path / "settings.json")
    logger = EventLogger(directory=tmp_path / "logs", enabled=True)
    capture = FakeCapture(frames=frames if frames is not None else [bright_frame()])
    camera = Camera(capture)
    assert camera.open(0)  # otherwise every _iterate() counts a read failure
    landmarker = FakeLandmarker(landmarker_script if landmarker_script is not None else [])
    backend = FakeBackend()
    injector = Injector(backend, elevation or FakeElevation(False))
    core = AppCore(settings, logger, camera, lambda p: landmarker,
                   injector, hotkey_factory=None, clock=clock)
    core.landmarker = landmarker
    core.backend = backend
    core.camera_for_test = camera
    assert core.state.transition(State.PAUSED)
    core._rebuild_mapper()
    return core


def feed_pose(engine, landmarks, cursor, clock, frames=3):
    """Feed one pose for N frames; returns all events."""
    events = []
    for _ in range(frames):
        events += engine.process(HandFrame(landmarks, "Right", clock.now), cursor)
    return events


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
