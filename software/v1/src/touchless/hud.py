"""HUD + windows — PLAN.md §5, §9 (HUD decision: display-only).

All windows are display-only in daily use: the pill and the ring
window never take focus and never receive clicks (Qt
WA_ShowWithoutActivating + WA_TransparentForMouseEvents), so by
construction they cannot steal focus or clicks. Interaction happens
in the settings window, via the tray, or via keys (§9 decision).

Tokens (colours per mode, §8 Phase 0 artefact — named here, never
hard-coded elsewhere):
  PAUSED      amber  #E8A33D   TRACKING    teal   #2ED3C6
  HAND_LOST   red    #FF6B5E   DEGRADED    yellow #FFC53D
  ERROR       red    #FF4D4F   CALIBRATING blue   #4D9FFF
The pill fades when idle but never disappears while TRACKING (§5).
The hold ring is drawn around the SYSTEM cursor by RingWindow (a
fullscreen transparent window); the pill also shows a small hold
progress bar, satisfying both §1.1 item 9 (pill carries the ring)
and §5 (ring around the cursor).

SoundPlayer: distinct short beeps per event on Windows (winsound),
silent no-op elsewhere; always paired with a visual change (§5).
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox, QCheckBox, QTabWidget, QStackedWidget,
)

TOKENS = {
    "PAUSED": "#E8A33D",
    "TRACKING": "#2ED3C6",
    "HAND_LOST": "#FF6B5E",
    "DEGRADED": "#FFC53D",
    "ERROR": "#FF4D4F",
    "CALIBRATING": "#4D9FFF",
    "OFF": "#888888",
}
STATE_WORDS = {
    "PAUSED": "Paused", "TRACKING": "Tracking", "HAND_LOST": "Hand lost",
    "DEGRADED": "Degraded", "ERROR": "Error", "CALIBRATING": "Calibrating",
    "OFF": "Off",
}
PILL_MARGIN = 16
IDLE_FADE_AFTER_S = 5.0

# Standard MediaPipe hand connections (index pairs) for the skeleton.
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
    (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]

# Sound events -> (frequency Hz, duration ms). Distinct pitch per
# event, never one generic beep (§5).
SOUND_FREQUENCIES = {
    "activation": (880, 90), "click": (1320, 60), "drag_start": (660, 70),
    "drag_end": (520, 70), "error": (220, 140), "pause": (440, 90),
    "hand_lost": (330, 110), "reacquire": (990, 90), "degraded": (370, 110),
    "recovery": (1100, 90), "calibration_done": (1560, 120),
}


class SoundPlayer:
    """Plays short distinct beeps (Windows) or nothing (elsewhere)."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.played: list[str] = []  # diagnostic record (also used by tests)

    def play(self, name: str) -> None:
        self.played.append(name)
        if not self.enabled or name not in SOUND_FREQUENCIES:
            return
        freq, dur = SOUND_FREQUENCIES[name]
        try:
            import winsound  # noqa: PLC0415 (Windows only)
            threading.Thread(target=winsound.Beep, args=(freq, dur), daemon=True).start()
        except Exception:
            pass  # sound must never break the pipeline


class FakeSoundPlayer(SoundPlayer):
    """Recording player for tests (no audio hardware needed)."""

    def __init__(self):
        super().__init__(enabled=True)

    def play(self, name: str) -> None:
        self.played.append(name)


def _pill_position(corner: str, width: int, height: int, screen) -> tuple[int, int]:
    geo = screen.availableGeometry()
    x = geo.x() + PILL_MARGIN if "left" in corner else geo.x() + geo.width() - width - PILL_MARGIN
    y = geo.y() + PILL_MARGIN if "top" in corner else geo.y() + geo.height() - height - PILL_MARGIN
    return x, y


class HudPill(QWidget):
    """Compact corner pill: mode + gesture chip + hold progress (§5)."""

    def __init__(self, settings, screen=None):
        super().__init__()
        self.settings = settings
        self.screen = screen or QApplication.primaryScreen()
        self.state = "PAUSED"
        self.chip = "Idle"
        self.hold_progress: float | None = None
        self.transient: str | None = None
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._apply_idle_fade)
        self._idle_timer.start(1000)
        self._last_activity = 0.0
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(300, 64)
        self._place()

    def _place(self) -> None:
        scale = self.settings.hud_scale
        self.setFixedSize(int(300 * scale), int(64 * scale))
        x, y = _pill_position(self.settings.hud_corner, self.width(), self.height(), self.screen)
        self.move(x, y)

    def _apply_idle_fade(self) -> None:
        import time
        if self.state == "TRACKING" and time.monotonic() - self._last_activity > IDLE_FADE_AFTER_S:
            self.setWindowOpacity(self.settings.hud_idle_opacity)
        else:
            self.setWindowOpacity(self.settings.hud_opacity)

    def note_activity(self) -> None:
        import time
        self._last_activity = time.monotonic()
        self.setWindowOpacity(self.settings.hud_opacity)

    def set_state(self, state: str, chip: str = "Idle", hold_progress=None,
                  transient: str | None = None) -> None:
        self.state = state
        self.chip = chip
        self.hold_progress = hold_progress
        if transient is not None:
            self.transient = transient
        self.note_activity()
        self.update()

    def clear_transient(self) -> None:
        self.transient = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(TOKENS.get(self.state, "#888888"))
        painter.setBrush(QColor(10, 12, 18, 230))
        painter.setPen(QPen(color, 2))
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 18, 18)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(14, 14, 14, 14)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        word = STATE_WORDS.get(self.state, self.state)
        painter.drawText(36, 26, word)
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(200, 210, 220))
        painter.drawText(36, 46, self.chip)
        if self.transient:
            painter.setPen(QColor(255, 220, 130))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(14, self.height() - 8, self.transient[:60])
        if self.hold_progress is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(60, 70, 85))
            painter.drawRoundedRect(14, self.height() - 12, self.width() - 28, 5, 2, 2)
            painter.setBrush(color)
            painter.drawRoundedRect(14, self.height() - 12,
                                   int((self.width() - 28) * max(0.0, min(1.0, self.hold_progress))), 5, 2, 2)


class RingWindow(QWidget):
    """Fullscreen transparent window drawing the hold ring at the cursor."""

    def __init__(self, screen=None):
        super().__init__()
        self.screen = screen or QApplication.primaryScreen()
        self.cursor_pos: tuple[float, float] | None = None
        self.progress: float | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        geo = self.screen.geometry()
        self.setGeometry(geo)

    def set_hold(self, pos: tuple[float, float] | None, progress: float | None) -> None:
        self.cursor_pos = pos
        self.progress = progress
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self.cursor_pos is None or self.progress is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y = self.cursor_pos
        painter.setPen(QPen(QColor("#2ED3C6"), 3))
        painter.drawEllipse(int(x) - 26, int(y) - 26, 52, 52)
        painter.setPen(QPen(QColor("#FFFFFF"), 4))
        span = int(-360 * 16 * max(0.0, min(1.0, self.progress)))
        painter.drawArc(int(x) - 26, int(y) - 26, 52, 52, 90 * 16, span)


class PreviewPane(QWidget):
    """Toggleable camera + skeleton pane (calibration/diagnosis only)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Touchless — Camera preview")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setFixedSize(480, 360)
        self._image: QImage | None = None
        self._landmarks = None
        self._extra_hands = 0

    def update_frame(self, frame_bgr, landmarks, extra_hands: int = 0) -> None:
        import numpy as np  # noqa: PLC0415
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        h, w = rgb.shape[:2]
        self._image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._landmarks = landmarks
        self._extra_hands = extra_hands
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(8, 10, 14))
        if self._image is not None:
            painter.drawImage(self.rect(), self._image)
        if self._landmarks:
            painter.setPen(QPen(QColor("#2ED3C6"), 2))
            w, h = self.width(), self.height()
            pts = [(int(x * w), int(y * h)) for x, y, _ in self._landmarks]
            for a, b in HAND_CONNECTIONS:
                painter.drawLine(pts[a][0], pts[a][1], pts[b][0], pts[b][1])
            painter.setBrush(QColor("#FFFFFF"))
            for x, y in pts:
                painter.drawEllipse(x - 3, y - 3, 6, 6)
        if self._extra_hands:
            painter.setPen(QColor(255, 200, 90))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(10, 20, "Extra hand ignored.")


class CalibrationWindow(QWidget):
    """Fullscreen calibration screen: targets + progress + fallbacks.

    Targets are drawn at screen positions; the user points at each
    target and pinch-holds until the ring completes to capture it
    (never a mouse click, §2 J3). Redo-one-point, Skip-to-defaults
    and Cancel are real buttons AND keyboard reachable.
    """

    redo_requested = pyqtSignal(int)  # point index to redo
    skip_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, screen=None):
        super().__init__()
        self.screen = screen or QApplication.primaryScreen()
        self.setWindowTitle("Touchless — Calibration")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        geo = self.screen.geometry()
        self.setGeometry(geo)
        self.targets: list[tuple[int, int]] = []
        self.current = 0
        self.captured: set[int] = set()
        layout = QVBoxLayout(self)
        layout.addStretch()
        self._label = QLabel("Calibration")
        self._label.setStyleSheet("color: white; font-size: 22px;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)
        row = QHBoxLayout()
        self._redo = QPushButton("Redo this point (R)")
        self._skip = QPushButton("Skip to defaults (S)")
        self._cancel = QPushButton("Cancel (C)")
        self._redo.clicked.connect(lambda: self.redo_requested.emit(self.current))
        self._skip.clicked.connect(self.skip_requested.emit)
        self._cancel.clicked.connect(self.cancel_requested.emit)
        row.addWidget(self._redo)
        row.addWidget(self._skip)
        row.addWidget(self._cancel)
        layout.addLayout(row)

    def set_targets(self, targets, current: int, captured) -> None:
        self.targets = targets
        self.current = current
        self.captured = set(captured)
        total = len(targets)
        self._label.setText(
            f"Point at the highlighted target and pinch-hold until the ring completes.\n"
            f"{len(captured)} of {total} captured.")
        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        key = event.key()
        if key == Qt.Key.Key_R:
            self.redo_requested.emit(self.current)
        elif key == Qt.Key.Key_S:
            self.skip_requested.emit()
        elif key == Qt.Key.Key_C:
            self.cancel_requested.emit()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(8, 10, 14, 235))
        for i, (x, y) in enumerate(self.targets):
            if i in self.captured:
                painter.setPen(QPen(QColor("#2ED3C6"), 3))
                painter.setBrush(QColor(46, 211, 198, 60))
            elif i == self.current:
                painter.setPen(QPen(QColor("#FFC53D"), 4))
                painter.setBrush(QColor(255, 197, 61, 60))
            else:
                painter.setPen(QPen(QColor(120, 130, 145), 2))
                painter.setBrush(QColor(0, 0, 0, 0))
            painter.drawEllipse(x - 34, y - 34, 68, 68)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.drawText(x - 8, y + 6, str(i + 1))


class FirstRunWizard(QDialog):
    """First-run walkthrough (§2 J1) as a stacked dialog.

    Steps: welcome -> camera check -> positioning -> calibration ->
    micro-tasks (move, click, scroll, pause) -> kill-switch drill ->
    done. Every step skippable; the driver in app.py marks micro-tasks
    done from live pipeline events.
    """

    STEPS = ["welcome", "camera", "positioning", "calibration",
             "task_move", "task_click", "task_scroll", "task_pause",
             "killswitch", "done"]
    STEP_TITLES = {
        "welcome": "Welcome — your webcam watches your hand",
        "camera": "Camera check",
        "positioning": "Get positioned",
        "calibration": "Calibration",
        "task_move": "Try it: move",
        "task_click": "Try it: click",
        "task_scroll": "Try it: scroll",
        "task_pause": "Try it: pause and resume",
        "killswitch": "Kill-switch drill",
        "done": "You're ready",
    }
    STEP_TEXT = {
        "welcome": "Your webcam watches your hand. Nothing is recorded or sent anywhere.\n\nPress Esc any time to stop.",
        "camera": "Checking the camera… (status updates live)",
        "positioning": "Sit as you normally would. Rest your elbow if you can.\nOpen the camera preview from the tray to see yourself in frame.",
        "calibration": "Point at each target and pinch-hold until the ring completes.\nYou can skip to defaults and calibrate later from Settings.",
        "task_move": "Move the cursor with your hand. (Or Skip.)",
        "task_click": "Pinch quickly to click. (Or Skip.)",
        "task_scroll": "Open your palm and move it up/down to scroll. (Or Skip.)",
        "task_pause": "Pause with F9 or a held fist, then show your open palm to resume. (Or Skip.)",
        "killswitch": "Now pause it with F9 or a held fist. Good — you can always do that.\nEsc quits the controller entirely.",
        "done": "Daily use starts PAUSED. Show your open palm to start controlling.\nThe gesture card is in Settings any time you need it.",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Touchless — First run")
        self.setFixedSize(520, 340)
        self._index = 0
        self.done_tasks: set[str] = set()
        self._stack = QStackedWidget()
        self._status: dict[str, QLabel] = {}
        for step in self.STEPS:
            page = QWidget()
            layout = QVBoxLayout(page)
            title = QLabel(self.STEP_TITLES[step])
            title.setStyleSheet("font-size: 17px; font-weight: bold;")
            layout.addWidget(title)
            layout.addWidget(QLabel(self.STEP_TEXT[step]))
            status = QLabel("")
            self._status[step] = status
            layout.addWidget(status)
            layout.addStretch()
            self._stack.addWidget(page)
        main = QVBoxLayout(self)
        main.addWidget(self._stack)
        row = QHBoxLayout()
        self._back = QPushButton("Back")
        self._skip = QPushButton("Skip")
        self._next = QPushButton("Next")
        self._back.clicked.connect(self._on_back)
        self._skip.clicked.connect(self._on_next)
        self._next.clicked.connect(self._on_next)
        row.addWidget(self._back)
        row.addStretch()
        row.addWidget(self._skip)
        row.addWidget(self._next)
        main.addLayout(row)
        self._refresh()

    def _refresh(self) -> None:
        self._stack.setCurrentIndex(self._index)
        self._back.setEnabled(self._index > 0)
        self._next.setText("Finish" if self._index == len(self.STEPS) - 1 else "Next")

    def _on_back(self) -> None:
        self._index = max(0, self._index - 1)
        self._refresh()

    def _on_next(self) -> None:
        if self._index >= len(self.STEPS) - 1:
            self.accept()
            return
        self._index += 1
        self._refresh()

    def current_step(self) -> str:
        return self.STEPS[self._index]

    def mark_task_done(self, step: str) -> None:
        self.done_tasks.add(step)
        self._status[step].setText("Done ✓ — press Next to continue.")
        if self.current_step() == step:
            self._refresh()

    def set_camera_status(self, text: str) -> None:
        self._status["camera"].setText(text)


class SettingsWindow(QDialog):
    """Two-tab settings window over settings.Settings (mouse+keyboard).

    Sliders show their default value in the label; clamps explain
    themselves inline (E14); Reset to defaults is always visible.
    """

    recalibrate_requested = pyqtSignal()

    def __init__(self, settings, cameras: list[int]):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("Touchless — Settings")
        self.setFixedSize(560, 520)
        tabs = QTabWidget()
        daily = QWidget()
        advanced = QWidget()
        tabs.addTab(daily, "Daily")
        tabs.addTab(advanced, "Advanced")
        self._clamp_label = QLabel("")
        self._clamp_label.setStyleSheet("color: #FFC53D;")
        self._sliders: dict[str, QSlider] = {}
        self._build_daily(daily)
        self._build_advanced(advanced, cameras)
        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(self._clamp_label)
        row = QHBoxLayout()
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._on_reset)
        recal = QPushButton("Recalibrate…")
        recal.clicked.connect(self.recalibrate_requested.emit)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(reset)
        row.addWidget(recal)
        row.addStretch()
        row.addWidget(close)
        main.addLayout(row)

    # ------------------------------------------------------------ builders
    def _slider_row(self, layout, label: str, key: str, lo: int, hi: int,
                    value: int, default: int, fmt="{v}"):
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{label} (default: {fmt.format(v=default)})"))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        slider.setSingleStep(1)
        val_label = QLabel(fmt.format(v=value))
        slider.valueChanged.connect(
            lambda v, k=key, lab=val_label: self._on_slider(k, v, lab, fmt))
        self._sliders[key] = slider
        row.addWidget(slider)
        row.addWidget(val_label)
        layout.addLayout(row)

    def _on_slider(self, key: str, value, label, fmt) -> None:
        # Scaled slider keys (sensitivity_x10, hud_scale_x100,
        # hud_opacity_x100) only preview here; the real float value is
        # applied in accept() so no stray attribute is ever stored.
        if key.endswith("_x10") or key.endswith("_x100"):
            label.setText(fmt.format(v=value))
            return
        applied, note = self.settings.set(key, value)
        label.setText(fmt.format(v=applied))
        if note:
            self._clamp_label.setText(note)

    def _build_daily(self, page) -> None:
        layout = QVBoxLayout(page)
        s = self.settings
        row = QHBoxLayout()
        row.addWidget(QLabel("Pause key (default: F9)"))
        self._pause_btn = QPushButton(s.pause_key)
        self._pause_btn.clicked.connect(lambda: self._capture_key("pause_key", self._pause_btn))
        row.addWidget(self._pause_btn)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Quit key (default: Escape)"))
        self._quit_btn = QPushButton(s.quit_key)
        self._quit_btn.clicked.connect(lambda: self._capture_key("quit_key", self._quit_btn))
        row.addWidget(self._quit_btn)
        layout.addLayout(row)
        self._slider_row(layout, "Sensitivity", "sensitivity_x10", 5, 20,
                         int(s.sensitivity * 10), 10, fmt="{v}")
        # Sensitivity is stored as a float; the slider above edits x10
        # and is reconciled in _on_slider via the special key below.
        corner = QComboBox()
        corner.addItems(["top-left", "top-right", "bottom-left", "bottom-right"])
        corner.setCurrentText(s.hud_corner)
        corner.currentTextChanged.connect(lambda v: setattr(s, "hud_corner", v))
        row = QHBoxLayout()
        row.addWidget(QLabel("HUD corner"))
        row.addWidget(corner)
        layout.addLayout(row)
        self._slider_row(layout, "HUD size %", "hud_scale_x100", 75, 150,
                         int(s.hud_scale * 100), 100, fmt="{v}%")
        self._slider_row(layout, "HUD opacity %", "hud_opacity_x100", 40, 100,
                         int(s.hud_opacity * 100), 90, fmt="{v}%")
        sound = QCheckBox("Sound on")
        sound.setChecked(s.sound_enabled)
        sound.toggled.connect(lambda v: setattr(s, "sound_enabled", v))
        layout.addWidget(sound)
        layout.addStretch()

    def _build_advanced(self, page, cameras) -> None:
        layout = QVBoxLayout(page)
        s = self.settings
        preset = QComboBox()
        preset.addItems(["steady", "balanced", "responsive"])
        preset.setCurrentText(s.smoothing_preset)
        preset.currentTextChanged.connect(lambda v: setattr(s, "smoothing_preset", v))
        row = QHBoxLayout()
        row.addWidget(QLabel("Smoothing preset (default: balanced)"))
        row.addWidget(preset)
        layout.addLayout(row)
        self._slider_row(layout, "Dead zone (px)", "dead_zone_px", 0, 15,
                         s.dead_zone_px, 3)
        self._slider_row(layout, "Hold time (ms)", "hold_time_ms", 300, 2000,
                         s.hold_time_ms, 600)
        self._slider_row(layout, "Drag threshold (px)", "drag_threshold_px", 4, 40,
                         s.drag_threshold_px, 12)
        self._slider_row(layout, "Scroll lines per step", "scroll_lines_per_step", 1, 10,
                         s.scroll_lines_per_step, 3)
        self._slider_row(layout, "Rest prompt (min, 0 = off)", "rest_prompt_minutes", 0, 60,
                         s.rest_prompt_minutes, 20)
        cam = QComboBox()
        cam.addItems([str(i) for i in cameras] or ["0"])
        cam.setCurrentText(str(s.camera_index))
        cam.currentTextChanged.connect(lambda v: setattr(s, "camera_index", int(v)))
        row = QHBoxLayout()
        row.addWidget(QLabel("Camera"))
        row.addWidget(cam)
        layout.addLayout(row)
        mirror = QCheckBox("Mirror hand left-right (hand-right → cursor-right)")
        mirror.setChecked(s.mirror_x)
        mirror.toggled.connect(lambda v: setattr(s, "mirror_x", v))
        layout.addWidget(mirror)
        for gesture, label in [("click", "Click (quick pinch)"),
                               ("hold_click", "Hold-confirm click"),
                               ("scroll", "Scroll (open-palm move)"),
                               ("drag", "Drag"),
                               ("gesture_pause", "Gesture-pause (held fist)")]:
            box = QCheckBox(f"Enable: {label}")
            box.setChecked(s.gestures_enabled.get(gesture, True))
            box.toggled.connect(
                lambda v, g=gesture: s.gestures_enabled.__setitem__(g, v))
            layout.addWidget(box)
        layout.addStretch()

    # ------------------------------------------------------------ actions
    def _on_reset(self) -> None:
        self.settings.reset_to_defaults()
        # Sync every slider to the fresh defaults BEFORE accept(), or
        # accept() would reconcile the three scaled sliders back to
        # their stale pre-reset positions (found by test, 2026-10-28).
        for key, slider in self._sliders.items():
            if key.endswith("_x10"):
                slider.setValue(int(getattr(self.settings, key[:-4]) * 10))
            elif key.endswith("_x100"):
                slider.setValue(int(getattr(self.settings, key[:-5]) * 100))
            else:
                slider.setValue(int(getattr(self.settings, key)))
        self._clamp_label.setText("Settings reset to defaults.")
        self.accept()  # reopening rebuilds controls from defaults

    def _capture_key(self, attr: str, button: QPushButton) -> None:
        button.setText("Press a key…")
        self._capturing = (attr, button)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        capturing = getattr(self, "_capturing", None)
        if capturing:
            attr, button = capturing
            key = event.key()
            name = _qt_key_name(key, event.text())
            if name:
                setattr(self.settings, attr, name)
                button.setText(name)
            self._capturing = None
            return
        super().keyPressEvent(event)

    # The Daily-tab sliders edit x10/x100 integers; reconcile them
    # into the float settings when the dialog closes.
    def accept(self) -> None:  # noqa: N802 (Qt naming)
        s = self.settings
        if "sensitivity_x10" in self._sliders:
            s.set("sensitivity", self._sliders["sensitivity_x10"].value() / 10.0)
        if "hud_scale_x100" in self._sliders:
            s.set("hud_scale", self._sliders["hud_scale_x100"].value() / 100.0)
        if "hud_opacity_x100" in self._sliders:
            s.set("hud_opacity", self._sliders["hud_opacity_x100"].value() / 100.0)
        self.settings.save()
        super().accept()


def _qt_key_name(key: int, text: str) -> str | None:
    """Map a Qt key press to a pynput key name (settings storage)."""
    special = {
        Qt.Key.Key_Escape: "Escape", Qt.Key.Key_F9: "F9", Qt.Key.Key_F10: "F10",
        Qt.Key.Key_Space: "space", Qt.Key.Key_Tab: "tab", Qt.Key.Key_Return: "enter",
    }
    if key in special:
        return special[key]
    if text and len(text) == 1:
        return text.lower()
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
        return f"F{key - Qt.Key.Key_F1 + 1}"
    return None
