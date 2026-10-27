"""Local-only event logging — PLAN.md §1.1 item 15.

Session events (activations, clicks, false-trigger reports, hand-lost
counts, FPS) are written as JSON lines to a per-session file under the
user data directory. Nothing is transmitted anywhere — this module
imports no networking code at all. Logging is toggleable from
Settings; when off, events are dropped (never buffered for later).

Test artefacts (§7.7): the event log is what feeds the §7 metrics
(false-trigger rate, task times, FPS distribution).
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from .settings import user_data_dir

# Event types (kept stable: test scripts and the §7 analysis read them)
ACTIVATION = "activation"
CLICK = "click"
HOLD_CLICK = "hold_click"
SCROLL = "scroll"
DRAG_START = "drag_start"
DRAG_END = "drag_end"
HAND_LOST = "hand_lost"
HAND_REACQUIRED = "hand_reacquired"
STATE_CHANGE = "state_change"
FALSE_TRIGGER = "false_trigger"
FPS_SAMPLE = "fps_sample"
ERROR = "error"
CALIBRATION = "calibration"
QUIT = "quit"


class EventLogger:
    """Thread-safe JSON-lines session logger. Local only."""

    def __init__(self, directory: Path | None = None, enabled: bool = True):
        self.directory = directory or (user_data_dir() / "logs")
        self.enabled = enabled
        self.session_id = uuid.uuid4().hex[:12]
        self._lock = threading.Lock()
        self._file = None
        self._counts: dict[str, int] = {}

    @property
    def path(self) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return self.directory / f"session-{stamp}-{self.session_id}.jsonl"

    def _open(self):
        if self._file is None:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._file = open(self.path, "a", encoding="utf-8")
            self._prune()

    def _prune(self, keep: int = 10) -> None:
        try:
            files = sorted(self.directory.glob("session-*.jsonl"))
            for old in files[:-keep]:
                old.unlink(missing_ok=True)
        except OSError:
            pass

    def log(self, event_type: str, detail: dict | None = None) -> None:
        if not self.enabled:
            return
        record = {
            "ts": time.time(),
            "session": self.session_id,
            "type": event_type,
            "detail": detail or {},
        }
        with self._lock:
            self._counts[event_type] = self._counts.get(event_type, 0) + 1
            try:
                self._open()
                self._file.write(json.dumps(record) + "\n")
                self._file.flush()
            except OSError:
                pass  # logging must never crash the controller

    def count(self, event_type: str) -> int:
        with self._lock:
            return self._counts.get(event_type, 0)

    def report_false_trigger(self, context: str) -> None:
        """A user-reported (or gate-closed) unintended injection.

        Both conditions from PLAN.md §7.4 apply at analysis time: the
        user says "I didn't mean that" AND the log shows an injection.
        This call records the report side of that pair.
        """
        self.log(FALSE_TRIGGER, {"context": context})

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                try:
                    self._file.close()
                except OSError:
                    pass
                self._file = None
