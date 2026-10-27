"""System tray — PLAN.md §1.1 item 1, §3.

The tray icon ALWAYS reflects the current state (§3: every
transition changes the tray icon together with the HUD and sound).
Menu: Pause/Resume, Recalibrate, Settings, Re-acquire hand, Quit.
Quit follows the watchdog shutdown path in app.py (tray Quit must
work even if the inference thread hangs, §2 J6).

Icons are drawn in code (no asset files): a coloured dot + state
initial, using the same tokens as hud.py.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from .hud import TOKENS

STATE_INITIALS = {
    "PAUSED": "P", "TRACKING": "T", "HAND_LOST": "H",
    "DEGRADED": "D", "ERROR": "E", "CALIBRATING": "C", "OFF": "O",
}
STATE_WORDS = {
    "PAUSED": "Paused", "TRACKING": "Tracking", "HAND_LOST": "Hand lost",
    "DEGRADED": "Degraded", "ERROR": "Error", "CALIBRATING": "Calibrating",
    "OFF": "Off",
}


def make_icon(state: str) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(TOKENS.get(state, "#888888")))
    painter.setPen(QColor(255, 255, 255))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
    painter.drawText(0, 0, 64, 64, 0x84, STATE_INITIALS.get(state, "?"))
    painter.end()
    return QIcon(pix)


class TrayBackend:
    """Interface so tests can drive the controller without Qt tray."""

    def set_icon(self, state: str) -> None:
        raise NotImplementedError

    def set_tooltip(self, text: str) -> None:
        raise NotImplementedError

    def set_pause_label(self, paused: bool) -> None:
        raise NotImplementedError


class QtTrayBackend(TrayBackend):
    def __init__(self, actions: dict):
        self.tray = QSystemTrayIcon()
        menu = QMenu()
        self._pause_action = menu.addAction("Pause")
        self._pause_action.triggered.connect(actions["pause_resume"])
        recal = menu.addAction("Recalibrate…")
        recal.triggered.connect(actions["recalibrate"])
        settings = menu.addAction("Settings…")
        settings.triggered.connect(actions["settings"])
        reacquire = menu.addAction("Re-acquire hand")
        reacquire.triggered.connect(actions["reacquire"])
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(actions["quit"])
        self.tray.setContextMenu(menu)
        self.tray.show()

    def set_icon(self, state: str) -> None:
        self.tray.setIcon(make_icon(state))

    def set_tooltip(self, text: str) -> None:
        self.tray.setToolTip(text)

    def set_pause_label(self, paused: bool) -> None:
        self._pause_action.setText("Resume" if paused else "Pause")


class FakeTrayBackend(TrayBackend):
    """Recording backend for tests."""

    def __init__(self):
        self.icons: list[str] = []
        self.tooltips: list[str] = []
        self.pause_labels: list[bool] = []

    def set_icon(self, state: str) -> None:
        self.icons.append(state)

    def set_tooltip(self, text: str) -> None:
        self.tooltips.append(text)

    def set_pause_label(self, paused: bool) -> None:
        self.pause_labels.append(paused)


class TrayController:
    """Owns the tray backend; mirrors state changes (never silent)."""

    def __init__(self, backend: TrayBackend):
        self.backend = backend
        self.state = "OFF"

    def set_state(self, state: str) -> None:
        self.state = state
        self.backend.set_icon(state)
        self.backend.set_tooltip(f"Touchless V1 — {STATE_WORDS.get(state, state)}")
        self.backend.set_pause_label(state == "PAUSED")
