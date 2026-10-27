"""Model-layer tests — PLAN.md §1.1 item 2 (one-hand rule), §9 E9."""

import os

import pytest

from touchless.model import (
    FakeLandmarker, ModelMissingError, PrimaryHandTracker,
)
from conftest import hand_result, open_palm_landmarks

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models",
                          "hand_landmarker.task")


def test_first_largest_hand_locks_and_stays():
    tracker = PrimaryHandTracker()
    small = hand_result(open_palm_landmarks(), "Right", area=0.03)
    big = hand_result(open_palm_landmarks(), "Left", area=0.08)
    primary, extra, lost = tracker.update([small, big])
    assert primary.handedness == "Left" and extra == 1 and not lost
    # A bigger hand appearing later must NOT displace the primary
    # (the primary hand is still present alongside it).
    bigger = hand_result(open_palm_landmarks(), "Right", area=0.20)
    primary, extra, lost = tracker.update([big, bigger])
    assert primary.handedness == "Left"
    assert extra == 1
    assert not lost


def test_primary_lost_does_not_auto_promote():
    tracker = PrimaryHandTracker()
    tracker.update([hand_result(open_palm_landmarks(), "Right", area=0.05)])
    primary, extra, lost = tracker.update(
        [hand_result(open_palm_landmarks(), "Left", area=0.09)])
    assert primary is None and lost is True  # different hand: no auto-switch
    tracker.clear_lock()
    primary, extra, lost = tracker.update(
        [hand_result(open_palm_landmarks(), "Left", area=0.09)])
    assert primary is not None and primary.handedness == "Left"


def test_no_hands_reports_not_lost_when_never_locked():
    tracker = PrimaryHandTracker()
    primary, extra, lost = tracker.update([])
    assert primary is None and extra == 0 and lost is False


def test_fake_landmarker_cycles_script():
    script = [[hand_result(open_palm_landmarks())], []]
    fake = FakeLandmarker(script)
    assert len(fake.process(None, 0)) == 1
    assert fake.process(None, 0) == []
    assert len(fake.process(None, 0)) == 1  # cycles
    fake.close()
    assert fake.closed


def test_bundled_model_file_present():
    assert os.path.exists(MODEL_PATH)
    assert os.path.getsize(MODEL_PATH) > 1_000_000  # a real task bundle


def test_missing_model_raises_e9_error():
    from touchless.model import MediaPipeLandmarker
    with pytest.raises(ModelMissingError):
        MediaPipeLandmarker("/nonexistent/path/hand_landmarker.task")


@pytest.mark.skipif(
    os.environ.get("TOUCHLESS_SKIP_MEDIAPIPE") == "1",
    reason="mediapipe not installed in this environment",
)
def test_real_landmarker_loads_and_reads_blank_frame():
    """Real MediaPipe load test (no webcam): a blank frame has no hands.

    Skipped automatically when mediapipe cannot be imported.
    """
    pytest.importorskip("mediapipe")
    import numpy as np
    from touchless.model import MediaPipeLandmarker
    landmarker = MediaPipeLandmarker(MODEL_PATH)
    try:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        assert landmarker.process(blank, 0) == []
    finally:
        landmarker.close()
