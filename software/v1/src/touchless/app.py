"""Application orchestration — PLAN.md §2, §3, §8.

AppCore is Qt-free (pipeline, safety, watchdog) so the whole core
loop is testable headless. The Qt shell at the bottom (TouchlessQtApp)
only renders AppCore's snapshot + event queue into windows.

Safety invariants enforced here, not by convention:
- Injection happens ONLY while the state machine is TRACKING or
  DEGRADED (G-GATE). Any injection attempt otherwise is refused and
  logged as a false-trigger defect.
- Quit ALWAYS releases a held mouse button first (J6), even when
  the inference thread is hung (join timeout -> os._exit last resort).
- ERROR never goes straight to TRACKING; CALIBRATING only from
  PAUSED (state.py enforces both).
- No network anywhere in this module (local only, §1.1 item 15).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

from . import __version__
from .camera import Camera, Diagnosis
from .gestures import (
    CURSOR_LANDMARK, EV_CLICK, EV_DRAG_END, EV_DRAG_START, EV_GATE,
    EV_HOLD_CLICK, EV_HOLD_PROGRESS, EV_PAUSE_GESTURE, EV_POSE, EV_SCROLL,
    POSE_FIST, POSE_NONE, POSE_OPEN_PALM, POSE_PINCH, GestureEngine,
    HandFrame,
)
from .injection import FakeBackend, InjectionBlocked, Injector
from .logging import (
    ACTIVATION, CALIBRATION, CLICK, DRAG_END, DRAG_START, ERROR, FPS_SAMPLE,
    HAND_LOST, HAND_REACQUIRED, HOLD_CLICK, QUIT, SCROLL, STATE_CHANGE,
    EventLogger,
)
from .mapping import CalibrationMap, CursorMapper
from .model import MediaPipeLandmarker, ModelMissingError, PrimaryHandTracker
from .settings import Settings, user_data_dir
from .state import State, StateMachine

# ---------------------------------------------------------------- errors
# Exact spec wording (PLAN.md §4). Do not paraphrase into jargon.
ERROR_TEXT = {
    "E1": ("No camera found. Check it's connected and not disabled in BIOS/Device Manager.",
           "Retry / Open settings help / Quit"),
    "E2": ("Camera access is off. Go to Settings > Privacy & security > Camera, and turn on "
           "'Let desktop apps access your camera', then Retry.",
           "Retry after changing the setting"),
    "E3": ("Camera is in use by another app (e.g. a video call). Close it or choose another camera.",
           "Camera picker / Retry"),
    "E4": ("No hand found yet. Put your hand in the frame and face a light source — or use defaults and retry.",
           "Repositioning guide / Use defaults / Retry"),
    "E5": ("Hand lost — move your hand back into view.",
           "Move hand back into view (auto-resume, no re-click)"),
    "E7": ("Light is low — tracking may be less reliable. Face a light source and avoid a window "
           "behind you. Continue degraded, or pause.",
           "Continue degraded / Pause"),
    "E8": ("Running slowly — close heavy apps or lower the camera resolution in Settings.",
           "Lower resolution / close apps / Pause"),
    "E9": ("Hand-tracking model is missing. Connect once to download it, or place the model file here — then Retry.",
           "Retry / place model file / Quit"),
    "E13": ("That click wasn't meant? Press {pause_key} to pause, and it won't happen again until you activate.",
            "Pause key; false trigger logged for tuning"),
    "E14": ("Settings reset to defaults.",
            "Reset to defaults (always available by mouse/keyboard)"),
}

# E7/E8 starting thresholds (pending pilot tuning, not measured floors).
LOW_LIGHT_MEAN = 40.0
LIGHT_RECOVER_MEAN = 60.0
LOW_FPS = 12.0
RECOVER_FPS = 20.0
DEGRADE_EVAL_INTERVAL_S = 5.0
READ_FAIL_STREAK_LIMIT = 5
TRANSIENT_SHOW_S = 4.0
WATCHDOG_STALL_S = 5.0
QUIT_JOIN_TIMEOUT_S = 3.0


def default_model_path() -> Path:
    override = os.environ.get("TOUCHLESS_MODEL_PATH")
    if override:
        return Path(override)
    # src/touchless/app.py -> v1/models/hand_landmarker.task
    return Path(__file__).resolve().parent.parent.parent / "models" / "hand_landmarker.task"


def chip_for_pose(pose: str, state: State) -> str:
    if pose == POSE_OPEN_PALM:
        return "Open palm — hold to activate" if state is State.PAUSED else "Open palm — scrolling"
    if pose == POSE_PINCH:
        return "Pinch — click"
    if pose == POSE_FIST:
        return "Fist — pause"
    return "Idle"


# ---------------------------------------------------------------- hotkeys
def _pynput_key(name: str):
    """Map a settings key name to a pynput key (None if unknown)."""
    from pynput.keyboard import Key, KeyCode  # noqa: PLC0415 (lazy)
    lower = name.lower()
    special = {
        "escape": Key.esc, "esc": Key.esc, "f9": Key.f9, "f10": Key.f10,
        "space": Key.space, "enter": Key.enter, "tab": Key.tab,
    }
    if lower in special:
        return special[lower]
    if lower.startswith("f") and lower[1:].isdigit():
        return getattr(Key, lower, None)
    if len(name) == 1:
        return KeyCode.from_char(name.lower())
    return None


class PynputHotkeys:
    """Global pause/quit keys (pynput listener, own thread)."""

    def __init__(self, pause_key: str, quit_key: str, on_pause, on_quit):
        self._pause = _pynput_key(pause_key)
        self._quit = _pynput_key(quit_key)
        self._on_pause = on_pause
        self._on_quit = on_quit
        self._pressed: set = set()
        self._listener = None

    def start(self) -> None:
        from pynput.keyboard import Listener  # noqa: PLC0415 (lazy)
        self._listener = Listener(on_press=self._press, on_release=self._release)
        self._listener.start()

    def _press(self, key) -> None:
        if key in self._pressed:
            return  # ignore auto-repeat
        self._pressed.add(key)
        try:
            if self._quit is not None and key == self._quit:
                self._on_quit()
            elif self._pause is not None and key == self._pause:
                self._on_pause()
        except Exception:
            pass

    def _release(self, key) -> None:
        self._pressed.discard(key)

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass


class FakeHotkeys:
    """Test hotkeys: trigger actions directly."""

    def __init__(self, on_pause, on_quit):
        self._on_pause = on_pause
        self._on_quit = on_quit
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def press_pause(self) -> None:
        self._on_pause()

    def press_quit(self) -> None:
        self._on_quit()


# ---------------------------------------------------------------- calibration
class CalibrationSession:
    """5-point capture (4 corners + centre, §2 J3).

    Points are captured by hold-confirm while pointing at the target
    (never a mouse click). Already-captured points survive a hand
    loss or a redo of one point; cancel keeps the previous profile;
    skip uses defaults for this session without overwriting the
    stored profile.
    """

    def __init__(self, screen_width: int, screen_height: int):
        inset_x = int(screen_width * 0.10)
        inset_y = int(screen_height * 0.10)
        self.targets = [
            (inset_x, inset_y), (screen_width - inset_x, inset_y),
            (inset_x, screen_height - inset_y), (screen_width - inset_x, screen_height - inset_y),
            (screen_width // 2, screen_height // 2),
        ]
        self.captured: dict[int, tuple[float, float]] = {}
        self.current = 0

    @property
    def complete(self) -> bool:
        return len(self.captured) == len(self.targets)

    def capture(self, hand_point) -> bool:
        """Capture the current target. Returns True when now complete."""
        self.captured[self.current] = hand_point
        self._advance()
        return self.complete

    def _advance(self) -> None:
        for i in range(len(self.targets)):
            if i not in self.captured:
                self.current = i
                return
        self.current = len(self.targets) - 1

    def redo(self, index: int) -> None:
        self.captured.pop(index, None)
        self.current = index

    def build_map(self, screen_width: int, screen_height: int) -> CalibrationMap:
        pairs = [(self.captured[i], self.targets[i]) for i in sorted(self.captured)]
        return CalibrationMap.from_points(pairs, screen_width, screen_height)


# ---------------------------------------------------------------- first run
class WizardDriver:
    """First-run step machine (§2 J1). Qt-free; the window is a view."""

    STEPS = ["welcome", "camera", "positioning", "calibration",
             "task_move", "task_click", "task_scroll", "task_pause",
             "killswitch", "done"]

    def __init__(self):
        self.index = 0
        self.done: set[str] = set()
        self.camera_status = ""
        self._move_accum = 0.0
        self._last_cursor: tuple[float, float] | None = None

    @property
    def step(self) -> str:
        return self.STEPS[self.index]

    def advance(self) -> None:
        self.index = min(self.index + 1, len(self.STEPS) - 1)

    def skip(self) -> None:
        self.advance()

    def complete(self, step: str) -> None:
        self.done.add(step)

    # Pipeline hooks (called by AppCore while the wizard is active).
    def on_cursor(self, pos) -> None:
        if self.step == "task_move" and self._last_cursor is not None:
            self._move_accum += abs(pos[0] - self._last_cursor[0]) + abs(pos[1] - self._last_cursor[1])
            if self._move_accum > 150.0:
                self.complete("task_move")
        self._last_cursor = pos

    def on_click(self) -> None:
        if self.step == "task_click":
            self.complete("task_click")

    def on_scroll(self) -> None:
        if self.step == "task_scroll":
            self.complete("task_scroll")

    def on_pause(self) -> None:
        if self.step == "task_pause":
            self.complete("task_pause")
        if self.step == "killswitch":
            self.complete("killswitch")


# ---------------------------------------------------------------- core
class AppCore:
    """Qt-free controller core: pipeline, safety, watchdog, shutdown."""

    def __init__(self, settings: Settings, logger: EventLogger, camera: Camera,
                 landmarker_factory, injector: Injector,
                 hotkey_factory=None, clock=None):
        self.settings = settings
        self.logger = logger
        self.camera = camera
        self.landmarker_factory = landmarker_factory
        self.injector = injector
        self._clock = clock or time.monotonic
        self.state = StateMachine(State.OFF)
        self.state.subscribe(self._on_transition)
        self.tracker = PrimaryHandTracker()
        self.engine = GestureEngine(
            hold_time_ms=settings.hold_time_ms,
            drag_threshold_px=settings.drag_threshold_px,
            scroll_lines_per_step=settings.scroll_lines_per_step,
            gestures_enabled=dict(settings.gestures_enabled),
            clock=self._clock,
        )
        self.mapper: CursorMapper | None = None
        self.landmarker = None
        self.calibration: CalibrationSession | None = None
        self.wizard = WizardDriver()
        self.wizard_active = False
        self._events: list = []
        self._events_lock = threading.Lock()
        self._snap_lock = threading.Lock()
        self._snapshot: dict = {
            "state": "OFF", "chip": "Idle", "hold_progress": None,
            "cursor_pos": None, "transient": None, "transient_until": 0.0,
            "preview_frame": None, "preview_landmarks": None, "extra_hands": 0,
            "fps": 0.0, "brightness": 0.0,
            "calibration": None, "wizard": None, "error": None,
        }
        self._stop_event = threading.Event()
        self._shutting_down = False
        self._pipeline_thread: threading.Thread | None = None
        self._watchdog_thread: threading.Thread | None = None
        self._heartbeat = 0.0
        self._stall_reported = False
        self._hotkeys = None
        self._hotkey_factory = hotkey_factory
        self._read_fail_streak = 0
        self._brightness_hist: deque = deque(maxlen=30)
        self._last_degrade_eval = 0.0
        self._degraded_reasons: set[str] = set()
        self._tracking_since: float | None = None
        self._rest_prompted_for_block = False
        self._dragging = False
        self._no_hand_since: float | None = None
        self._e4_shown = False

    # ------------------------------------------------------------ events
    def _on_transition(self, event) -> None:
        with self._events_lock:
            self._events.append(event)
        self.logger.log(STATE_CHANGE, {
            "from": event.previous.value, "to": event.current.value,
            "error": event.error_id,
        })

    def drain_events(self) -> list:
        with self._events_lock:
            events, self._events = self._events, []
        return events

    def snapshot(self) -> dict:
        with self._snap_lock:
            snap = dict(self._snapshot)
            if snap["calibration"] is not None:
                snap["calibration"] = dict(snap["calibration"])
            return snap

    def _set_snapshot(self, **values) -> None:
        with self._snap_lock:
            self._snapshot.update(values)

    def _set_transient(self, text: str | None) -> None:
        self._set_snapshot(transient=text,
                           transient_until=self._clock() + TRANSIENT_SHOW_S if text else 0.0)

    # ------------------------------------------------------------ lifecycle
    def start(self) -> bool:
        """Launch: camera + model preconditions, then PAUSED (default).

        Launch failures go OFF -> PAUSED -> ERROR so the transition
        table (§3, which has no OFF -> ERROR edge) is respected; the
        intermediate PAUSED is never presented (no drain happens in
        between). Returns False when the app lands in ERROR.
        """
        self.state.transition(State.PAUSED)
        # Camera precondition.
        try:
            opened = self.camera.open(self.settings.camera_index)
        except PermissionError:
            return self._fail("E2")
        if not opened:
            diag = self.camera.diagnose()
            if diag == Diagnosis.ABSENT:
                return self._fail("E1")
            if diag == Diagnosis.PERMISSION:
                return self._fail("E2")
            return self._fail("E3")
        # Model precondition (bundled file; E9 when missing/corrupt).
        try:
            self.landmarker = self.landmarker_factory(default_model_path())
        except ModelMissingError:
            return self._fail("E9")
        self._rebuild_mapper()
        self._stop_event.clear()
        self._pipeline_thread = threading.Thread(target=self._pipeline_loop, daemon=True)
        self._pipeline_thread.start()
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        if self._hotkey_factory is not None:
            self._hotkeys = self._hotkey_factory(self._toggle_pause, self.shutdown)
            self._hotkeys.start()
        return True

    def _fail(self, error_id: str) -> bool:
        message, _action = ERROR_TEXT[error_id]
        if error_id == "E9":
            message = message + f" Expected location: {default_model_path()}"
        self.state.to_error(error_id, message)
        self._set_snapshot(error=(error_id, message))
        self.logger.log(ERROR, {"id": error_id, "message": message})
        return False

    def retry_from_error(self) -> bool:
        """Retry action from ERROR: re-check preconditions, then PAUSED."""
        if self.state.state is not State.ERROR:
            return False
        try:
            opened = self.camera.open(self.settings.camera_index)
        except PermissionError:
            return self._fail("E2")
        if not opened:
            return self._fail("E3")
        if self.landmarker is None:
            try:
                self.landmarker = self.landmarker_factory(default_model_path())
            except ModelMissingError:
                return self._fail("E9")
        self._rebuild_mapper()
        self.state.clear_error()  # ERROR -> PAUSED only, never TRACKING
        self._set_snapshot(error=None)
        return True

    def _rebuild_mapper(self) -> None:
        width, height = self.injector.screen_size()
        profile = self.settings.active_profile_obj
        targets = [
            (0, 0), (width - 1, 0), (0, height - 1),
            (width - 1, height - 1), (width // 2, height // 2),
        ]
        stored = [profile.points.top_left, profile.points.top_right,
                  profile.points.bottom_left, profile.points.bottom_right,
                  profile.points.centre]
        pairs = [(hp, tp) for hp, tp in zip(stored, targets) if hp is not None]
        if len(pairs) >= 3:
            mapping = CalibrationMap.from_points(pairs, width, height)
        else:
            mapping = CalibrationMap.default(width, height)
        self.mapper = CursorMapper(
            mapping, mirror_x=self.settings.mirror_x,
            preset=self.settings.smoothing_preset,
            dead_zone_px=self.settings.dead_zone_px,
            sensitivity=self.settings.sensitivity,
        )

    # ------------------------------------------------------------ actions
    def _pause(self) -> None:
        if self.state.state in (State.TRACKING, State.HAND_LOST, State.DEGRADED):
            self._release_drag()
            self.engine.reset()
            self.state.transition(State.PAUSED)
            self.wizard.on_pause()

    def _resume(self) -> None:
        """Deliberate activation equivalent (key/tray). Gate still
        blocks every non-deliberate path; see BUILD_NOTES.md."""
        if self.state.state is State.PAUSED:
            self.engine.reset()
            self.state.transition(State.TRACKING)
            self.logger.log(ACTIVATION, {"via": "key_or_tray"})

    def _toggle_pause(self) -> None:
        if self.state.state in (State.TRACKING, State.HAND_LOST, State.DEGRADED):
            self._pause()
        elif self.state.state is State.PAUSED:
            self._resume()

    def _release_drag(self) -> None:
        if self._dragging:
            self.injector.release_all()
            self._dragging = False

    def reacquire(self) -> None:
        """Explicit re-acquire (§1.1 item 2): clear the hand lock."""
        self.tracker.clear_lock()
        if self.state.state is State.HAND_LOST:
            self.engine.reset()

    def start_calibration(self) -> None:
        """CALIBRATING is reachable only from PAUSED (§3)."""
        if self.state.state in (State.TRACKING, State.HAND_LOST, State.DEGRADED):
            self._pause()
        if self.state.state is not State.PAUSED:
            return
        width, height = self.injector.screen_size()
        self.calibration = CalibrationSession(width, height)
        self.engine.reset()
        self.state.transition(State.CALIBRATING)
        self._set_snapshot(calibration={
            "targets": self.calibration.targets,
            "current": 0, "captured": [],
        })

    def calibration_redo(self, index: int) -> None:
        if self.calibration is not None:
            self.calibration.redo(index)
            self._sync_calibration_snapshot()

    def calibration_skip(self) -> None:
        """Use defaults for this session; stored profile untouched."""
        if self.calibration is None:
            return
        width, height = self.injector.screen_size()
        self.mapper = CursorMapper(
            CalibrationMap.default(width, height),
            mirror_x=self.settings.mirror_x,
            preset=self.settings.smoothing_preset,
            dead_zone_px=self.settings.dead_zone_px,
            sensitivity=self.settings.sensitivity,
        )
        self.calibration = None
        self._set_snapshot(calibration=None)
        self.logger.log(CALIBRATION, {"result": "skipped_to_defaults"})
        self.state.transition(State.PAUSED)

    def calibration_cancel(self) -> None:
        if self.calibration is None:
            return
        self.calibration = None
        self._set_snapshot(calibration=None)
        self.logger.log(CALIBRATION, {"result": "cancelled_profile_kept"})
        self.state.transition(State.PAUSED)

    def _finish_calibration(self) -> None:
        assert self.calibration is not None
        width, height = self.injector.screen_size()
        mapping = self.calibration.build_map(width, height)
        profile = self.settings.active_profile_obj
        pts = self.calibration.captured
        profile.points.top_left = pts.get(0)
        profile.points.top_right = pts.get(1)
        profile.points.bottom_left = pts.get(2)
        profile.points.bottom_right = pts.get(3)
        profile.points.centre = pts.get(4)
        profile.screen_width = width
        profile.screen_height = height
        self.settings.save()
        self.mapper = CursorMapper(
            mapping, mirror_x=self.settings.mirror_x,
            preset=self.settings.smoothing_preset,
            dead_zone_px=self.settings.dead_zone_px,
            sensitivity=self.settings.sensitivity,
        )
        self.calibration = None
        self._set_snapshot(calibration=None)
        self.logger.log(CALIBRATION, {"result": "complete", "points": 5})
        self.state.transition(State.PAUSED)

    def _sync_calibration_snapshot(self) -> None:
        if self.calibration is None:
            return
        self._set_snapshot(calibration={
            "targets": self.calibration.targets,
            "current": self.calibration.current,
            "captured": sorted(self.calibration.captured),
        })

    # ------------------------------------------------------------ injection
    def _safe_inject(self, fn, *args) -> bool:
        """G-GATE: refuse + log any injection while not injecting."""
        if not self.state.is_injecting:
            self.logger.report_false_trigger("injection attempted while gate closed")
            return False
        try:
            fn(*args)
            return True
        except InjectionBlocked:
            from .injection import E10_MESSAGE  # noqa: PLC0415
            self._set_transient(E10_MESSAGE)
            self.logger.log(ERROR, {"id": "E10", "message": E10_MESSAGE})
            return False
        except Exception as exc:
            self.logger.log(ERROR, {"id": "inject", "message": str(exc)})
            return False

    # ------------------------------------------------------------ pipeline
    def _pipeline_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._iterate()
            except Exception as exc:
                self.logger.log(ERROR, {"id": "pipeline", "message": str(exc)})
            if not self._stop_event.is_set():
                time.sleep(0.002)

    def _iterate(self) -> None:
        self._heartbeat = self._clock()
        if self.state.state is State.OFF:
            return
        ok, frame, brightness = self.camera.read()
        if not ok or frame is None:
            self._read_fail_streak += 1
            if self._read_fail_streak >= READ_FAIL_STREAK_LIMIT:
                if self.state.state is not State.ERROR:
                    self._fail("E1")
            return
        self._read_fail_streak = 0
        self._brightness_hist.append(brightness)
        now = self._clock()
        try:
            hands = self.landmarker.process(frame, int(now * 1000)) if self.landmarker else []
        except Exception as exc:
            self.logger.log(ERROR, {"id": "model", "message": str(exc)})
            hands = []
        primary, extra, _lost = self.tracker.update(hands)
        cursor_pos = None
        raw_pos = None
        if primary is not None and self.mapper is not None:
            anchor = primary.landmarks[CURSOR_LANDMARK]
            cursor_pos = self.mapper.update(anchor[0], anchor[1], now)
            raw_pos = self.mapper.map_raw(anchor[0], anchor[1])
        self._set_snapshot(
            cursor_pos=cursor_pos, fps=self.camera.fps, brightness=brightness,
            preview_frame=frame,
            preview_landmarks=primary.landmarks if primary else None,
            extra_hands=extra,
        )
        state = self.state.state
        if state is State.CALIBRATING:
            self._update_calibration(primary, cursor_pos, raw_pos)
        elif state is State.PAUSED:
            if primary is not None:
                self._no_hand_since = None
                self._e4_shown = False
                events = self.engine.process(
                    HandFrame(primary.landmarks, primary.handedness, now),
                    cursor_pos, raw_pos)
                for event in events:
                    if event.kind == EV_GATE:
                        self.engine.reset()
                        self.state.transition(State.TRACKING)
                        self.logger.log(ACTIVATION, {"via": "gate_pose"})
                        self._tracking_since = now
            else:
                # E4: no hand for the first-run timeout -> guidance,
                # never an infinite spinner. Guidance only (PAUSED is
                # not an error state); "Use defaults" is the
                # calibration-skip path, always available.
                if self._no_hand_since is None:
                    self._no_hand_since = now
                elif not self._e4_shown and now - self._no_hand_since >= 10.0:
                    message, _ = ERROR_TEXT["E4"]
                    self._set_transient(message)
                    self._e4_shown = True
        elif state in (State.TRACKING, State.DEGRADED):
            if primary is None:
                self._release_drag()
                self.engine.reset()
                self.state.transition(State.HAND_LOST)
                self.logger.log(HAND_LOST, {})
                self._set_snapshot(hold_progress=None)
            else:
                self._update_tracking(primary, cursor_pos, now, raw_pos)
                self._evaluate_degradation(now)
        elif state is State.HAND_LOST:
            if primary is not None:
                self.engine.reset()
                self.state.transition(State.TRACKING)
                self.logger.log(HAND_REACQUIRED, {})
                self._tracking_since = now
        # Rest prompt (suggestion only, never a lockout, §6).
        if state is State.TRACKING and self.settings.rest_prompt_minutes > 0:
            if self._tracking_since and not self._rest_prompted_for_block:
                elapsed_min = (now - self._tracking_since) / 60.0
                if elapsed_min >= self.settings.rest_prompt_minutes:
                    self._set_transient(
                        "You've been gesturing a while — consider resting your arm.")
                    self._rest_prompted_for_block = True
        if state is not State.TRACKING:
            self._tracking_since = None
            self._rest_prompted_for_block = False
        if self.wizard_active and cursor_pos is not None:
            self.wizard.on_cursor(cursor_pos)

    def _update_tracking(self, primary, cursor_pos, now: float,
                         raw_pos=None) -> None:
        events = self.engine.process(
            HandFrame(primary.landmarks, primary.handedness, now),
            cursor_pos, raw_pos)
        chip = "Idle"
        hold_progress = None
        for event in events:
            kind = event.kind
            if kind == EV_POSE:
                chip = chip_for_pose(event.data["pose"], self.state.state)
            elif kind == EV_CLICK:
                if self._safe_inject(self.injector.click):
                    self.logger.log(CLICK, {})
                    self.wizard.on_click()
            elif kind == EV_HOLD_CLICK:
                if self._safe_inject(self.injector.click):
                    self.logger.log(HOLD_CLICK, {})
                    self.wizard.on_click()
            elif kind == EV_HOLD_PROGRESS:
                hold_progress = event.data["progress"]
            elif kind == EV_DRAG_START:
                if self._safe_inject(self.injector.mouse_down):
                    self._dragging = True
                    self.logger.log(DRAG_START, {})
            elif kind == EV_DRAG_END:
                self.injector.release_all()
                self._dragging = False
                self.logger.log(DRAG_END, {})
            elif kind == EV_SCROLL:
                if self._safe_inject(self.injector.scroll, event.data["lines"]):
                    self.logger.log(SCROLL, {"lines": event.data["lines"]})
                    self.wizard.on_scroll()
            elif kind == EV_PAUSE_GESTURE:
                self._pause()
        # Cursor follows the hand 1:1 (never eased) while injecting.
        if cursor_pos is not None:
            self._safe_inject(self.injector.move, cursor_pos[0], cursor_pos[1])
        self._set_snapshot(chip=chip, hold_progress=hold_progress)
        if hold_progress is None:
            pass  # ring window clears when progress is None (shell reads this)

    def _update_calibration(self, primary, cursor_pos, raw_pos=None) -> None:
        if primary is None or cursor_pos is None or self.calibration is None:
            return
        now = self._clock()
        events = self.engine.process(
            HandFrame(primary.landmarks, primary.handedness, now),
            cursor_pos, raw_pos)
        hold_progress = None
        for event in events:
            if event.kind == EV_HOLD_PROGRESS:
                hold_progress = event.data["progress"]
            elif event.kind == EV_HOLD_CLICK:
                hand_point = self.mapper.mirror_point(
                    primary.landmarks[CURSOR_LANDMARK][0],
                    primary.landmarks[CURSOR_LANDMARK][1])
                if self.calibration.capture(hand_point):
                    self._finish_calibration()
                    return
                self._sync_calibration_snapshot()
        self._set_snapshot(hold_progress=hold_progress)
        self._sync_calibration_snapshot()

    def _evaluate_degradation(self, now: float) -> None:
        if now - self._last_degrade_eval < DEGRADE_EVAL_INTERVAL_S:
            return
        self._last_degrade_eval = now
        state = self.state.state
        if state not in (State.TRACKING, State.DEGRADED):
            return
        # E7 low light (mean of a full window of recent frames — a single
        # dark frame must not flip the state; ~1 s of evidence first).
        if len(self._brightness_hist) >= 30:
            mean_brightness = sum(self._brightness_hist) / len(self._brightness_hist)
            if mean_brightness < LOW_LIGHT_MEAN:
                self._degraded_reasons.add("light")
            elif mean_brightness > LIGHT_RECOVER_MEAN:
                self._degraded_reasons.discard("light")
        # E8 low FPS: step down resolution first (§6 ladder), then DEGRADED.
        fps = self.camera.fps
        if fps > 0 and fps < LOW_FPS:
            if not self.camera.step_down_resolution():
                self._degraded_reasons.add("fps")
            self.logger.log(FPS_SAMPLE, {"fps": round(fps, 1)})
        elif fps >= RECOVER_FPS:
            self._degraded_reasons.discard("fps")
        if self._degraded_reasons and state is State.TRACKING:
            reason = "E7" if "light" in self._degraded_reasons else "E8"
            message, _ = ERROR_TEXT[reason]
            self._set_transient(message)
            self.state.transition(State.DEGRADED)
        elif not self._degraded_reasons and state is State.DEGRADED:
            self.state.transition(State.TRACKING)

    # ------------------------------------------------------------ watchdog
    def _watchdog_loop(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(0.5)
            if self._stop_event.is_set():
                return
            age = self._clock() - self._heartbeat if self._heartbeat else 0.0
            if age > WATCHDOG_STALL_S and not self._stall_reported:
                self._stall_reported = True
                self.logger.log(ERROR, {"id": "watchdog",
                                        "message": f"pipeline heartbeat stale for {age:.1f}s"})
            elif age <= WATCHDOG_STALL_S:
                self._stall_reported = False

    # ------------------------------------------------------------ shutdown
    def shutdown(self) -> None:
        """J6: button-up -> camera release -> thread join -> quit.

        If the pipeline thread does not die within the join timeout,
        the process is force-exited: tray Quit must kill the process
        even when inference hangs. Button-up is attempted BEFORE the
        join so a stuck drag is released even on the forced path.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        try:
            self.injector.release_all()
        except Exception:
            pass
        self._stop_event.set()
        try:
            self.camera.release()
        except Exception:
            pass
        try:
            if self.landmarker is not None:
                self.landmarker.close()
        except Exception:
            pass
        try:
            if self._hotkeys is not None:
                self._hotkeys.stop()
        except Exception:
            pass
        if self._pipeline_thread is not None and self._pipeline_thread.is_alive():
            self._pipeline_thread.join(timeout=QUIT_JOIN_TIMEOUT_S)
            if self._pipeline_thread.is_alive():
                os._exit(0)  # last resort: the process must die (J6)
        try:
            self.logger.log(QUIT, {})
            self.logger.close()
        except Exception:
            pass
        if self.state.state is not State.OFF:
            self.state.transition(State.OFF)


# ---------------------------------------------------------------- Qt shell
class TouchlessQtApp:
    """Renders AppCore into Qt windows. All logic stays in AppCore."""

    def __init__(self, core: AppCore, first_run: bool):
        from PyQt6.QtWidgets import QApplication  # noqa: PLC0415 (Qt shell)
        from PyQt6.QtCore import QTimer  # noqa: PLC0415
        from .hud import (CalibrationWindow, FirstRunWizard, HudPill,  # noqa: PLC0415
                          PreviewPane, RingWindow, SettingsWindow, SoundPlayer)
        from .tray import QtTrayBackend, TrayController  # noqa: PLC0415
        self.core = core
        self.app = QApplication(sys.argv)
        self.sound = SoundPlayer(enabled=core.settings.sound_enabled)
        self.pill = HudPill(core.settings)
        self.ring = RingWindow()
        self.preview = PreviewPane()
        self.tray = TrayController(QtTrayBackend({
            "pause_resume": core._toggle_pause,
            "recalibrate": core.start_calibration,
            "settings": self._open_settings,
            "reacquire": core.reacquire,
            "quit": self._quit,
        }))
        self.cal_window = None
        self.wizard_window = None
        self.first_run = first_run
        self.pill.show()
        self.ring.show()
        self._timer = QTimer()
        self._timer.timeout.connect(self._drain)
        self._timer.start(50)

    def _open_settings(self) -> None:
        from .hud import SettingsWindow  # noqa: PLC0415
        cameras = self.core.camera.enumerate_devices()
        window = SettingsWindow(self.core.settings, cameras)
        window.recalibrate_requested.connect(self.core.start_calibration)
        if window.exec():
            self.core.settings.save()
            self.core._rebuild_mapper()
            self.pill._place()

    def _quit(self) -> None:
        self.core.shutdown()
        try:
            self.tray.backend.tray.hide()
        except Exception:
            pass
        self.app.quit()

    def _drain(self) -> None:
        for event in self.core.drain_events():
            if event.sound:
                self.sound.play(event.sound)
            if event.current is State.OFF:
                self._quit()
                return
        snap = self.core.snapshot()
        state = snap["state"]
        self.tray.set_state(state)
        transient = snap["transient"]
        if transient and self.core._clock() > snap["transient_until"]:
            transient = None
            self.pill.clear_transient()
        self.pill.set_state(state, snap["chip"], snap["hold_progress"], transient)
        if snap["hold_progress"] is not None and snap["cursor_pos"] is not None:
            self.ring.set_hold(snap["cursor_pos"], snap["hold_progress"])
        else:
            self.ring.set_hold(None, None)
        if self.preview.isVisible() and snap["preview_frame"] is not None:
            self.preview.update_frame(snap["preview_frame"],
                                      snap["preview_landmarks"],
                                      snap["extra_hands"])
        # Calibration window lifecycle follows the core session.
        cal = snap["calibration"]
        if cal is not None and self.cal_window is None:
            from .hud import CalibrationWindow  # noqa: PLC0415
            self.cal_window = CalibrationWindow()
            self.cal_window.redo_requested.connect(self.core.calibration_redo)
            self.cal_window.skip_requested.connect(self.core.calibration_skip)
            self.cal_window.cancel_requested.connect(self.core.calibration_cancel)
            self.cal_window.show()
        elif cal is None and self.cal_window is not None:
            self.cal_window.close()
            self.cal_window = None
        if self.cal_window is not None and cal is not None:
            self.cal_window.set_targets(cal["targets"], cal["current"], cal["captured"])
        # First-run wizard.
        if self.first_run and self.wizard_window is None:
            self.wizard_window = FirstRunWizard()
            self.wizard_window.show()
        if self.wizard_window is not None:
            wizard = self.core.wizard
            for step in list(wizard.done):
                self.wizard_window.mark_task_done(step)
            self.wizard_window.set_camera_status(
                f"Camera: {self.core.camera.width}x{self.core.camera.height} "
                f"@ {snap['fps']:.0f} fps")
            if not self.wizard_window.isVisible():
                self.first_run = False

    def run(self) -> int:
        return self.app.exec()


# ---------------------------------------------------------------- entry
def build_core(settings: Settings, camera=None, landmarker_factory=None,
                backend=None, hotkey_factory=None) -> AppCore:
    """Assemble AppCore with real defaults (tests override pieces)."""
    from .camera import Camera  # noqa: PLC0415
    from .injection import Injector, PyAutoGUIBackend  # noqa: PLC0415
    logger = EventLogger(enabled=settings.logging_enabled)
    camera = camera or Camera()
    injector = Injector(backend or PyAutoGUIBackend())
    if hotkey_factory is None:
        def hotkey_factory(on_pause, on_quit):
            return PynputHotkeys(settings.pause_key, settings.quit_key,
                                 on_pause, on_quit)
    return AppCore(settings, logger, camera,
                   landmarker_factory or MediaPipeLandmarker,
                   injector, hotkey_factory=hotkey_factory)


def main(argv=None) -> int:
    import argparse  # noqa: PLC0415
    parser = argparse.ArgumentParser(prog="touchless",
                                     description="Touchless Controller v1 — webcam control for Windows.")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--reset-settings", action="store_true")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--no-gui", action="store_true",
                        help="Run the core pipeline without Qt windows (testing).")
    args = parser.parse_args(argv)
    if args.version:
        print(f"Touchless Controller {__version__}")
        return 0
    settings_path = user_data_dir() / "settings.json"
    if args.reset_settings and settings_path.exists():
        settings_path.unlink()
    first_run = not settings_path.exists()
    settings = Settings.load(settings_path)
    if args.camera is not None:
        settings.camera_index = args.camera
    if args.profile is not None and args.profile in settings.profiles:
        settings.active_profile = args.profile
    if args.no_gui:
        core = build_core(settings, backend=FakeBackend(), hotkey_factory=None)
        if not core.start():
            print(f"Could not start: {core.state.error_message}")
            return 1
        print(f"Touchless Controller {__version__} running headless (Ctrl+C to stop).")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            core.shutdown()
        return 0
    core = build_core(settings)
    core.wizard_active = first_run
    ok = core.start()
    shell = TouchlessQtApp(core, first_run)
    if not ok:
        # ERROR state is already set; the shell shows the pill + tray
        # with the message so the user can Retry or Quit.
        pass
    return shell.run()
