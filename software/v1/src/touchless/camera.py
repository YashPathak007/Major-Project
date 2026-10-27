"""Camera layer — PLAN.md §2 J1, §9, §4 E1–E3.

Responsibilities: device select, frame capture, busy/permission/
absent diagnostics, resolution ladder (§6 degradation step 1).
Must never block the settings window behind camera load — opening
happens in the pipeline thread, and failures surface as ERROR states
with plain-language messages, never a hung UI.

Diagnosis distinguishes (risk table, §9):
  device absent            -> E1
  open fails (busy)        -> E3
  permission error         -> E2 (when the backend can tell; see note)
  frames consistently black -> BLACK_FRAMES (shutter/BIOS hint in help)
E2/E3 note (BUILD_NOTES.md): OpenCV cannot distinguish "camera busy"
from "desktop-apps camera switch off" — both look like an open
failure. The primary message for an open failure is E3, and the
error pane always offers the E2 Settings path as the next step; a
backend that raises PermissionError maps straight to E2.
"""

from __future__ import annotations

import collections
import time

import numpy as np

# Resolution ladder, highest first (§6 degradation step 1).
RESOLUTION_LADDER = [(1280, 720), (640, 480), (320, 240)]
BLACK_FRAME_MEAN = 8.0      # mean pixel value below this = black frame
BLACK_FRAME_STREAK = 10     # consecutive black frames before diagnosis
FPS_WINDOW = 30             # frames in the rolling FPS window


class Diagnosis:
    OK = "ok"
    ABSENT = "absent"
    BUSY = "busy"
    PERMISSION = "permission"
    BLACK_FRAMES = "black_frames"


class CaptureBackend:
    """Interface: open / read / release. Real = OpenCV, tests = fake."""

    def open(self, index: int, width: int, height: int) -> bool:
        raise NotImplementedError

    def read(self):
        """Returns (ok, frame_or_None). frame is a BGR numpy array."""
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError

    def is_opened(self) -> bool:
        raise NotImplementedError


class OpenCVCapture(CaptureBackend):
    """Real backend. cv2 is imported lazily (tests run without it)."""

    def __init__(self):
        import cv2  # noqa: PLC0415 (lazy: only needed with a real camera)
        self._cv2 = cv2
        self._cap = None

    def open(self, index: int, width: int, height: int) -> bool:
        import cv2  # noqa: PLC0415
        backend = cv2.CAP_DSHOW if _is_windows() else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(index, backend)
        if not self._cap.isOpened():
            self._cap = None
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        return True

    def read(self):
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read()
        return bool(ok), (frame if ok else None)

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()


def _is_windows() -> bool:
    import sys
    return sys.platform.startswith("win")


class FakeCapture(CaptureBackend):
    """Scripted backend for tests.

    frames: list of numpy arrays (or None for a failed read) cycled
    in order. open_fails: if True, open() returns False.
    permission_error: if True, open() raises PermissionError (E2 path).
    """

    def __init__(self, frames=None, open_fails: bool = False,
                 permission_error: bool = False):
        self.frames = list(frames) if frames else []
        self.open_fails = open_fails
        self.permission_error = permission_error
        self._opened = False
        self._i = 0
        self.released = False

    def open(self, index: int, width: int, height: int) -> bool:
        if self.permission_error:
            raise PermissionError("camera access denied (simulated)")
        if self.open_fails:
            return False
        self._opened = True
        return True

    def read(self):
        if not self._opened or not self.frames:
            return False, None
        frame = self.frames[self._i % len(self.frames)]
        self._i += 1
        return frame is not None, frame

    def release(self) -> None:
        self._opened = False
        self.released = True

    def is_opened(self) -> bool:
        return self._opened


def frame_brightness(frame) -> float:
    """Mean pixel value (0–255). Low values feed the E7 detector."""
    if frame is None:
        return 0.0
    return float(np.mean(frame))


class Camera:
    """Owns one capture backend + diagnostics + FPS + resolution ladder."""

    def __init__(self, backend: CaptureBackend | None = None, probe_factory=None):
        self.backend = backend or OpenCVCapture()
        # Probing must not disturb the main capture; tests inject a
        # probe factory to simulate absent/busy devices deterministically.
        self.probe_factory = probe_factory
        self.index = 0
        self.width, self.height = RESOLUTION_LADDER[0]
        self._ladder_pos = 0
        self._frame_times: collections.deque = collections.deque(maxlen=FPS_WINDOW)
        self._black_streak = 0
        self.opened = False

    # ------------------------------------------------------------ devices
    def enumerate_devices(self, max_index: int = 4) -> list[int]:
        """Probe indices for openable cameras (quick open + release)."""
        found = []
        probe = self.probe_factory() if self.probe_factory else self.backend.__class__()
        for idx in range(max_index):
            try:
                if probe.open(idx, 640, 480):
                    found.append(idx)
                    probe.release()
            except PermissionError:
                found.append(idx)  # present but permission-denied: still a device
            except Exception:
                pass
        return found

    def open(self, index: int | None = None) -> bool:
        if index is not None:
            self.index = index
        try:
            ok = self.backend.open(self.index, self.width, self.height)
        except PermissionError:
            raise
        self.opened = bool(ok)
        return self.opened

    def read(self):
        """Returns (ok, frame, brightness). Updates FPS + black streak."""
        ok, frame = self.backend.read()
        now = time.monotonic()
        if ok and frame is not None:
            self._frame_times.append(now)
            brightness = frame_brightness(frame)
            self._black_streak = self._black_streak + 1 if brightness < BLACK_FRAME_MEAN else 0
        else:
            brightness = 0.0
        return ok, frame, brightness

    @property
    def fps(self) -> float:
        if len(self._frame_times) < 2:
            return 0.0
        span = self._frame_times[-1] - self._frame_times[0]
        if span <= 0:
            return 0.0
        return (len(self._frame_times) - 1) / span

    @property
    def black_frames_sustained(self) -> bool:
        return self._black_streak >= BLACK_FRAME_STREAK

    def step_down_resolution(self) -> bool:
        """§6 ladder step 1. Returns False when already at the lowest."""
        if self._ladder_pos + 1 >= len(RESOLUTION_LADDER):
            return False
        self._ladder_pos += 1
        self.width, self.height = RESOLUTION_LADDER[self._ladder_pos]
        self.backend.release()
        self.opened = self.backend.open(self.index, self.width, self.height)
        return self.opened

    def diagnose(self) -> str:
        """Classify the camera situation (E1/E2/E3/black-frames/ok)."""
        if self.black_frames_sustained:
            return Diagnosis.BLACK_FRAMES
        if self.opened:
            return Diagnosis.OK
        try:
            if self.backend.open(self.index, self.width, self.height):
                self.opened = True
                return Diagnosis.OK
        except PermissionError:
            return Diagnosis.PERMISSION
        except Exception:
            pass
        devices = self.enumerate_devices()
        if not devices:
            return Diagnosis.ABSENT
        return Diagnosis.BUSY

    def release(self) -> None:
        try:
            self.backend.release()
        except Exception:
            pass
        self.opened = False
