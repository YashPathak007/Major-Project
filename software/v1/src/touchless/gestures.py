"""Gesture dictionary v1.0 — PLAN.md §1.2 (PROPOSED, pending elicitation).

Dictionary version: v1.0-proposed. The freeze rule (§1.2) says the
dictionary is frozen only after the Phase 0 elicitation (5–8 people,
MVP commands only). That elicitation has NOT run yet, so every entry
below is the plan's proposal, and the validation step belongs to Yash
+ volunteers — it is not claimed as done anywhere in this build.

One gesture = one meaning, no synonyms. The classifier is
deterministic rules over the 21 MediaPipe landmarks (no ML model in
v1, per §1.3). All thresholds below are starting values pending
pilot tuning (PLAN.md §6/§7.6); none is presented as a measured
optimum.

Landmark indices (MediaPipe Hands): 0 wrist; thumb 1–4 (tip 4);
index 5–8 (tip 8); middle 9–12 (tip 12); ring 13–16 (tip 16);
pinky 17–20 (tip 20). A finger counts as extended when its tip is
farther from the wrist than its PIP joint — an orientation-tolerant
rule that works for a hand facing the camera at any roll.

Pinch-session disambiguation (one pinch, three outcomes, decided by
time + movement so a gesture can never mean two things at once):
  quick release           -> G2 click (fires on release)
  hold, no move, ring done -> G3 hold-confirm click (fires on ring)
  hold + move past threshold, before the ring completes
                            -> G5 drag (button down on threshold
                               crossing, up on release)
Once the ring completes, that pinch session is consumed: later
movement does not start a drag (re-pinch to drag).

G4 scroll (NOT FROZEN — plan open question 1): implemented as the
leading candidate, open-palm vertical move. The Wobbrock fallback is
built in: scroll is a per-gesture setting (§1.1 item 12) — if
elicitation agreement is low, scroll is disabled as a gesture and
the user scrolls with the mouse wheel instead of forcing a gesture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# ------------------------------------------------------------ landmarks
WRIST = 0
THUMB_TIP, THUMB_IP = 4, 3
INDEX_TIP, INDEX_PIP = 8, 6
MIDDLE_TIP, MIDDLE_PIP = 12, 10
RING_TIP, RING_PIP = 16, 14
PINKY_TIP, PINKY_PIP = 20, 18
INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 5, 9, 17

# Cursor anchor: index fingertip (landmark 8). Smoothing + dead zone
# in mapping.py keep it steady enough for the 24 px acceptance test.
CURSOR_LANDMARK = INDEX_TIP

# Poses
POSE_NONE = "none"
POSE_OPEN_PALM = "open_palm"
POSE_PINCH = "pinch"
POSE_FIST = "fist"

# Events emitted by the engine
EV_GATE = "gate"                    # G0 held long enough -> activate
EV_CLICK = "click"                  # G2 quick pinch, on release
EV_HOLD_PROGRESS = "hold_progress"  # 0.0..1.0 while pinch held
EV_HOLD_CLICK = "hold_click"        # G3 ring completed
EV_DRAG_START = "drag_start"        # G5 threshold crossed while pinched
EV_DRAG_END = "drag_end"            # G5 pinch released mid-drag
EV_SCROLL = "scroll"                # G4 lines (positive = scroll up)
EV_PAUSE_GESTURE = "pause_gesture"  # fist held -> pause
EV_POSE = "pose"                    # current pose name, for the HUD chip

# Starting thresholds (pending pilot tuning, not measured optima)
EXTENSION_RATIO = 1.08   # tip farther than pip * ratio -> extended
PINCH_RATIO = 0.35       # thumb-index distance < ratio * palm size
GATE_HOLD_S = 0.35       # open palm held this long -> gate opens
PAUSE_HOLD_S = 0.70      # fist held this long -> pause
POSE_STABLE_FRAMES = 2   # a pose must persist this many frames
SCROLL_STEP_PX = 30.0    # cursor px of vertical move per scroll step
SCROLL_MIN_INTERVAL_S = 0.05


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class HandFrame:
    """One model's output for one hand, at one moment."""

    landmarks: list  # 21 (x, y, z) normalized triples
    handedness: str = "Right"  # MediaPipe label (image perspective)
    timestamp: float = 0.0

    @property
    def valid(self) -> bool:
        return len(self.landmarks) == 21


@dataclass
class GestureEvent:
    kind: str
    data: dict = field(default_factory=dict)


def _finger_extended(lm, tip: int, pip: int) -> bool:
    return _dist(lm[tip], lm[WRIST]) > _dist(lm[pip], lm[WRIST]) * EXTENSION_RATIO


def classify_pose(lm) -> tuple[str, float]:
    """Classify a static pose. Returns (pose, pinch_ratio).

    pinch_ratio is thumb-index distance / palm size (used by the
    session machine); it is meaningful for every pose.
    """
    palm = _dist(lm[WRIST], lm[MIDDLE_MCP])
    if palm <= 1e-6:
        return POSE_NONE, 1.0
    pinch_ratio = _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / palm
    fingers = (
        _finger_extended(lm, INDEX_TIP, INDEX_PIP),
        _finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP),
        _finger_extended(lm, RING_TIP, RING_PIP),
        _finger_extended(lm, PINKY_TIP, PINKY_PIP),
    )
    thumb = _finger_extended(lm, THUMB_TIP, THUMB_IP)
    if all(fingers) and thumb:
        return POSE_OPEN_PALM, pinch_ratio
    if not any(fingers) and not thumb:
        return POSE_FIST, pinch_ratio
    if pinch_ratio < PINCH_RATIO:
        return POSE_PINCH, pinch_ratio
    return POSE_NONE, pinch_ratio


class GestureEngine:
    """Stateful gesture interpretation over a stream of HandFrames.

    The engine is pure logic (no camera, no injection) so every rule
    is unit-testable with synthetic landmarks. It receives the mapped
    cursor position from the caller (drag/scroll thresholds are in
    screen pixels, matching the plan's behavioural acceptance tests).
    """

    def __init__(self, hold_time_ms: int = 600, drag_threshold_px: int = 12,
                 scroll_lines_per_step: int = 3,
                 gestures_enabled: dict | None = None,
                 clock=None):
        self.hold_time_s = hold_time_ms / 1000.0
        self.drag_threshold_px = drag_threshold_px
        self.scroll_lines_per_step = scroll_lines_per_step
        self.enabled = gestures_enabled or {
            "click": True, "hold_click": True, "scroll": True,
            "drag": True, "gesture_pause": True,
        }
        self._now = clock or __import__("time").monotonic
        self.reset()

    def reset(self) -> None:
        self._pose = POSE_NONE
        self._pose_frames = 0
        self._gate_since: float | None = None
        self._gate_fired = False
        self._fist_since: float | None = None
        self._fist_fired = False
        self._pinch: dict | None = None  # active pinch session
        self._scroll_anchor_y: float | None = None
        self._last_scroll_t = 0.0

    # ------------------------------------------------------------ main
    def process(self, frame: HandFrame, cursor_pos: tuple[float, float],
                raw_pos: tuple[float, float] | None = None) -> list[GestureEvent]:
        """Interpret one frame. Returns events (possibly empty).

        cursor_pos is the displayed (filtered) cursor. raw_pos, when
        given, is the unfiltered anchor in screen coordinates and is
        used for movement decisions (drag displacement, scroll delta):
        after a pose change the filtered cursor glides toward the new
        anchor for several frames, and that glide is not hand movement
        — measuring it would turn pinch-clicks into false drags.
        """
        events: list[GestureEvent] = []
        now = self._now()
        pose, _ = classify_pose(frame.landmarks)
        measure = raw_pos if raw_pos is not None else cursor_pos

        # Pose stability: a pose must persist POSE_STABLE_FRAMES frames
        # before it counts (kills single-frame flicker).
        if pose == self._pose:
            self._pose_frames += 1
        else:
            self._pose = pose
            self._pose_frames = 1
        stable_pose = pose if self._pose_frames >= POSE_STABLE_FRAMES else None
        events.append(GestureEvent(EV_POSE, {"pose": pose}))

        # --- G0 activation gate: open palm held briefly ---------------
        if stable_pose == POSE_OPEN_PALM:
            if self._gate_since is None:
                self._gate_since = now
            elif not self._gate_fired and now - self._gate_since >= GATE_HOLD_S:
                self._gate_fired = True
                events.append(GestureEvent(EV_GATE, {}))
        else:
            self._gate_since = None
            self._gate_fired = False

        # --- Gesture-pause: fist held ---------------------------------
        if self.enabled.get("gesture_pause", True) and stable_pose == POSE_FIST:
            if self._fist_since is None:
                self._fist_since = now
            elif not self._fist_fired and now - self._fist_since >= PAUSE_HOLD_S:
                self._fist_fired = True
                events.append(GestureEvent(EV_PAUSE_GESTURE, {}))
        else:
            self._fist_since = None
            self._fist_fired = False

        # --- Pinch session: G2 / G3 / G5 -------------------------------
        pinched = stable_pose == POSE_PINCH
        if pinched and self._pinch is None:
            self._pinch = {
                "start_t": now, "start_pos": measure,
                "ring_fired": False, "drag_started": False,
            }
        if self._pinch is not None:
            session = self._pinch
            if not pinched:
                # Release: decide what this pinch was.
                if session["drag_started"]:
                    events.append(GestureEvent(EV_DRAG_END, {}))
                elif session["ring_fired"]:
                    pass  # hold-click already fired; session consumed
                elif self.enabled.get("click", True):
                    events.append(GestureEvent(EV_CLICK, {}))
                self._pinch = None
            else:
                moved = math.hypot(measure[0] - session["start_pos"][0],
                                   measure[1] - session["start_pos"][1])
                held = now - session["start_t"]
                if (self.enabled.get("drag", True) and not session["drag_started"]
                        and not session["ring_fired"]
                        and moved >= self.drag_threshold_px):
                    session["drag_started"] = True
                    events.append(GestureEvent(EV_DRAG_START, {}))
                elif (self.enabled.get("hold_click", True) and not session["drag_started"]
                        and not session["ring_fired"]):
                    progress = min(held / self.hold_time_s, 1.0)
                    events.append(GestureEvent(EV_HOLD_PROGRESS, {"progress": progress}))
                    if held >= self.hold_time_s:
                        session["ring_fired"] = True
                        events.append(GestureEvent(EV_HOLD_CLICK, {}))

        # --- G4 scroll: open-palm vertical move (candidate, §1.2) -----
        if self.enabled.get("scroll", True) and stable_pose == POSE_OPEN_PALM:
            if self._scroll_anchor_y is None:
                self._scroll_anchor_y = measure[1]
            else:
                dy = measure[1] - self._scroll_anchor_y
                steps = int(dy / SCROLL_STEP_PX)
                if steps != 0 and now - self._last_scroll_t >= SCROLL_MIN_INTERVAL_S:
                    # Hand up (dy negative) -> scroll up (positive lines).
                    events.append(GestureEvent(
                        EV_SCROLL, {"lines": -steps * self.scroll_lines_per_step}))
                    self._scroll_anchor_y += steps * SCROLL_STEP_PX
                    self._last_scroll_t = now
        else:
            self._scroll_anchor_y = None

        return events
