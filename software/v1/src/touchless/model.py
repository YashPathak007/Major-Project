"""Hand-tracking model layer — PLAN.md §9.

Pinned MediaPipe Tasks Hand Landmarker (21 landmarks, CPU delegate,
bundled model file — no first-run download, E9 if the file is missing
or corrupt). The model returns up to 2 hands so the E6 second-hand
rule can be enforced (a second hand is detected and ignored); only
the primary hand ever drives input — that is the one-hand rule (§1.1
item 2). "1 hand" in the plan means one *controlled* hand; the
implementation note is recorded in BUILD_NOTES.md.

Primary-hand lock (one-hand rule):
- The first (largest) hand seen becomes primary and stays primary
  while present — never switched mid-drag, never switched because
  another hand grew larger.
- If the primary hand leaves, the tracker reports lost (the state
  machine goes HAND-LOST). A different hand does NOT auto-promote.
- Re-acquire is explicit: clear_lock() (tray action, or pause +
  re-gate), after which the next largest hand becomes primary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ModelMissingError(Exception):
    """The bundled model file is absent or unreadable (E9)."""


@dataclass
class HandResult:
    landmarks: list  # 21 (x, y, z) normalized triples
    handedness: str  # MediaPipe label, image perspective
    area: float = 0.0  # bounding-box area (for largest-hand choice)


class Landmarker:
    """Interface: process a BGR frame -> list of HandResult."""

    def process(self, frame_bgr, timestamp_ms: int) -> list[HandResult]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class MediaPipeLandmarker(Landmarker):
    """Real Tasks-vision HandLandmarker. mediapipe imported lazily."""

    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise ModelMissingError(f"Model file not found: {self.model_path}")
        try:
            import mediapipe as mp  # noqa: PLC0415 (lazy: heavy dep)
            base = mp.tasks.BaseOptions(model_asset_path=str(self.model_path))
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=base,
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=2,  # see module docstring: detection, not control
            )
            self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
            self._mp_image = mp.Image
            self._mp_format = mp.ImageFormat.SRGB
        except Exception as exc:
            raise ModelMissingError(f"Could not load model {self.model_path}: {exc}") from exc

    def process(self, frame_bgr, timestamp_ms: int) -> list[HandResult]:
        import numpy as np  # noqa: PLC0415
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])  # BGR -> RGB
        image = self._mp_image(image_format=self._mp_format, data=rgb)
        result = self._landmarker.detect_for_video(image, int(timestamp_ms))
        hands: list[HandResult] = []
        for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
            pts = [(lm.x, lm.y, lm.z) for lm in landmarks]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            label = handedness[0].category_name if handedness else "Right"
            hands.append(HandResult(landmarks=pts, handedness=label, area=area))
        return hands

    def close(self) -> None:
        try:
            self._landmarker.close()
        except Exception:
            pass


class FakeLandmarker(Landmarker):
    """Scripted landmarker for tests: yields one result list per call."""

    def __init__(self, script: list[list[HandResult]]):
        self.script = script
        self._i = 0
        self.closed = False

    def process(self, frame_bgr, timestamp_ms: int) -> list[HandResult]:
        if not self.script:
            return []
        result = self.script[self._i % len(self.script)]
        self._i += 1
        return result

    def close(self) -> None:
        self.closed = True


class PrimaryHandTracker:
    """One-hand lock over model outputs (see module docstring)."""

    def __init__(self):
        self.primary_handedness: str | None = None
        self.locked = False

    def update(self, hands: list[HandResult]):
        """Returns (primary_or_None, extra_hand_count, primary_lost)."""
        if not hands:
            return None, 0, self.locked
        if not self.locked:
            primary = max(hands, key=lambda h: h.area)
            self.primary_handedness = primary.handedness
            self.locked = True
            return primary, len(hands) - 1, False
        matches = [h for h in hands if h.handedness == self.primary_handedness]
        if matches:
            primary = max(matches, key=lambda h: h.area)
            return primary, len(hands) - 1, False
        return None, len(hands), True  # primary gone; others do not promote

    def clear_lock(self) -> None:
        """Explicit re-acquire (§1.1 item 2): next hand becomes primary."""
        self.primary_handedness = None
        self.locked = False
