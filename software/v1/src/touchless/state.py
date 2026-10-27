"""State machine — PLAN.md §3. Freeze: every transition has a HUD +
sound + tray change. No transition is silent.

Rules enforced here (not by convention in callers):
- ERROR never transitions straight to TRACKING (re-activation must
  be deliberate: ERROR -> PAUSED -> G0 -> TRACKING).
- CALIBRATING is reachable only from PAUSED.
- PAUSED is reachable from every live state.
- Injection state changes only through transitions, and every
  transition notifies listeners (HUD, tray, sound) together.

Illegal transitions return False and are logged by the caller; they
never raise inside the pipeline (a bad transition must not crash
the controller mid-gesture).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum


class State(Enum):
    OFF = "OFF"
    PAUSED = "PAUSED"
    CALIBRATING = "CALIBRATING"
    TRACKING = "TRACKING"
    HAND_LOST = "HAND_LOST"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


# Allowed transitions, exactly per the §3 table.
ALLOWED = {
    State.OFF: {State.PAUSED},
    State.PAUSED: {State.TRACKING, State.CALIBRATING, State.ERROR, State.OFF},
    State.TRACKING: {State.PAUSED, State.HAND_LOST, State.DEGRADED, State.ERROR, State.OFF},
    State.HAND_LOST: {State.TRACKING, State.PAUSED, State.DEGRADED, State.ERROR, State.OFF},
    State.DEGRADED: {State.TRACKING, State.PAUSED, State.HAND_LOST, State.ERROR, State.OFF},
    State.CALIBRATING: {State.PAUSED, State.ERROR, State.OFF},
    State.ERROR: {State.PAUSED, State.OFF},
}

# Sound event per transition (played by hud.SoundPlayer; always
# paired with the visual change, never the sole signal, §5).
SOUNDS = {
    (State.OFF, State.PAUSED): None,  # silence on launch is deliberate (§3)
    (State.PAUSED, State.TRACKING): "activation",
    (State.TRACKING, State.PAUSED): "pause",
    (State.HAND_LOST, State.PAUSED): "pause",
    (State.DEGRADED, State.PAUSED): "pause",
    (State.TRACKING, State.HAND_LOST): "hand_lost",
    (State.HAND_LOST, State.TRACKING): "reacquire",
    (State.TRACKING, State.DEGRADED): "degraded",
    (State.DEGRADED, State.TRACKING): "recovery",
    (State.HAND_LOST, State.DEGRADED): "degraded",
    (State.DEGRADED, State.HAND_LOST): "hand_lost",
    (State.CALIBRATING, State.PAUSED): "calibration_done",
    (State.ERROR, State.PAUSED): "recovery",
}
DEFAULT_SOUND = "error"  # any transition into ERROR


@dataclass
class TransitionEvent:
    previous: State
    current: State
    sound: str | None
    error_id: str | None = None
    error_message: str | None = None


class StateMachine:
    """The §3 state machine. Listeners get every transition."""

    def __init__(self, initial: State = State.OFF):
        self.state = initial
        self.error_id: str | None = None
        self.error_message: str | None = None
        self._listeners: list = []
        self._lock = threading.Lock()

    def subscribe(self, listener) -> None:
        self._listeners.append(listener)

    @property
    def is_injecting(self) -> bool:
        """Injection is live only in TRACKING or (flagged) DEGRADED."""
        return self.state in (State.TRACKING, State.DEGRADED)

    def transition(self, target: State, error_id: str | None = None,
                   error_message: str | None = None) -> bool:
        with self._lock:
            if target not in ALLOWED.get(self.state, set()):
                return False
            previous = self.state
            self.state = target
            if target is State.ERROR:
                self.error_id = error_id
                self.error_message = error_message
            else:
                self.error_id = None
                self.error_message = None
            sound = SOUNDS.get((previous, target))
            if target is State.ERROR and sound is None:
                sound = DEFAULT_SOUND
            event = TransitionEvent(previous, target, sound, self.error_id, self.error_message)
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                pass  # a HUD/tray listener must never break the machine
        return True

    # Convenience wrappers used by the pipeline (all go through
    # transition(), so the rules above always apply).
    def to_error(self, error_id: str, message: str) -> bool:
        return self.transition(State.ERROR, error_id, message)

    def clear_error(self) -> bool:
        """ERROR -> PAUSED only. Never straight to TRACKING (§3)."""
        if self.state is State.ERROR:
            return self.transition(State.PAUSED)
        return False
