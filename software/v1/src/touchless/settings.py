"""Settings for Touchless Controller v1 — PLAN.md §1.1 item 12.

Two levels maximum. Level 1 (daily): pause key, sensitivity, HUD
position/size/opacity, sound. Level 2 (Advanced): smoothing preset,
dead zone, hold time, camera choice, per-gesture enable/disable,
reset-to-defaults. Every value is clamped to a safe range and the
clamp is explained; "Reset to defaults" is always available; every
setting is reachable by mouse + keyboard (the settings window never
requires a gesture).

This module is pure data + JSON I/O (no Qt) so it is testable
headless. The settings *window* lives in hud.py as a view over this
model.

Hold-time default note (PLAN.md §6): the plan deliberately does NOT
pre-commit a millisecond value — the default is SET FROM PILOT DATA.
Until the pilot runs, the shipped default below (600 ms) is an
initial starting value, not a pilot result. It is recorded as such in
BUILD_NOTES.md.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def user_data_dir() -> Path:
    """Per-user data directory (Windows: %APPDATA%, else ~/.config)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "TouchlessV1"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "TouchlessV1"
    return Path.home() / ".config" / "TouchlessV1"


# ---------------------------------------------------------------- clamps
# name -> (min, max, explanation shown when a value is clamped)
CLAMPS = {
    "sensitivity": (0.5, 2.0, "Sensitivity is clamped to 0.5–2.0 — outside that range the cursor becomes unusable."),
    "hud_scale": (0.75, 1.5, "HUD size is clamped to 0.75–1.5."),
    "hud_opacity": (0.4, 1.0, "HUD opacity is clamped to 0.4–1.0 so the pill never becomes invisible."),
    "hud_idle_opacity": (0.3, 0.9, "Idle HUD opacity is clamped to 0.3–0.9 — the pill fades but never disappears while tracking."),
    "dead_zone_px": (0, 15, "Dead zone is clamped to 0–15 px."),
    "hold_time_ms": (300, 2000, "Hold time is clamped to 300–2000 ms — shorter would click without confirming."),
    "drag_threshold_px": (4, 40, "Drag threshold is clamped to 4–40 px — smaller would turn a trembling hold into a drag."),
    "rest_prompt_minutes": (0, 60, "Rest-prompt interval is clamped to 0–60 minutes (0 = off)."),
    "scroll_lines_per_step": (1, 10, "Scroll step is clamped to 1–10 lines."),
}

HUD_CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")
SMOOTHING_PRESETS = ("steady", "balanced", "responsive")


@dataclass
class CalibrationPoints:
    """Hand-space points captured during calibration.

    Keys: top_left, top_right, bottom_left, bottom_right, centre.
    Values are (hand_x, hand_y) in mirrored hand coordinates (see
    mapping.py: mirror is applied before the affine fit).
    """

    top_left: tuple | None = None
    top_right: tuple | None = None
    bottom_left: tuple | None = None
    bottom_right: tuple | None = None
    centre: tuple | None = None

    def captured(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def count(self) -> int:
        return len(self.captured())


@dataclass
class Profile:
    """One calibration profile. Default + one custom (PLAN.md §1.1 item 10)."""

    name: str = "Default"
    points: CalibrationPoints = field(default_factory=CalibrationPoints)
    hold_time_ms: int = 600
    screen_width: int = 1920
    screen_height: int = 1080

    def to_json(self) -> dict:
        data = asdict(self)
        # tuples become lists in JSON; restore on load
        data["points"] = {k: (list(v) if v else None) for k, v in data["points"].items()}
        return data

    @classmethod
    def from_json(cls, data: dict) -> "Profile":
        pts = data.get("points", {}) or {}
        points = CalibrationPoints(**{
            k: (tuple(v) if v else None) for k, v in pts.items()
        })
        return cls(
            name=data.get("name", "Default"),
            points=points,
            hold_time_ms=int(data.get("hold_time_ms", 600)),
            screen_width=int(data.get("screen_width", 1920)),
            screen_height=int(data.get("screen_height", 1080)),
        )


@dataclass
class Settings:
    """Full settings tree (two levels). All values validated on set."""

    # Level 1 — daily
    pause_key: str = "F9"
    quit_key: str = "Escape"
    sensitivity: float = 1.0
    hud_corner: str = "top-right"
    hud_scale: float = 1.0
    hud_opacity: float = 0.9
    hud_idle_opacity: float = 0.45
    sound_enabled: bool = True
    # Level 2 — Advanced
    smoothing_preset: str = "balanced"
    dead_zone_px: int = 3
    hold_time_ms: int = 600
    camera_index: int = 0
    mirror_x: bool = True
    drag_threshold_px: int = 12
    scroll_lines_per_step: int = 3
    rest_prompt_minutes: int = 20
    logging_enabled: bool = True
    gestures_enabled: dict = field(default_factory=lambda: {
        "click": True,
        "hold_click": True,
        "scroll": True,
        "drag": True,
        "gesture_pause": True,
    })
    profiles: dict = field(default_factory=lambda: {"Default": Profile(name="Default")})
    active_profile: str = "Default"

    # ------------------------------------------------------------ access
    def get(self, key: str):
        return getattr(self, key)

    def set(self, key: str, value, clamp_note: list | None = None):
        """Set a value, clamping to the safe range. Returns (applied, note).

        `note` is None when no clamp was needed, else the explanation
        string (shown inline in the settings window, PLAN.md E14).
        """
        if key in CLAMPS:
            lo, hi, explanation = CLAMPS[key]
            clamped = min(max(value, lo), hi)
            note = None if clamped == value else explanation
            setattr(self, key, clamped)
            if clamp_note is not None and note:
                clamp_note.append(note)
            return clamped, note
        if key == "hud_corner" and value not in HUD_CORNERS:
            raise ValueError(f"hud_corner must be one of {HUD_CORNERS}")
        if key == "smoothing_preset" and value not in SMOOTHING_PRESETS:
            raise ValueError(f"smoothing_preset must be one of {SMOOTHING_PRESETS}")
        setattr(self, key, value)
        return value, None

    def reset_to_defaults(self) -> None:
        """Restore every setting to defaults (E14). Profiles are kept."""
        fresh = Settings()
        keep_profiles = self.profiles
        keep_active = self.active_profile if self.active_profile in keep_profiles else "Default"
        self.__dict__.update(fresh.__dict__)
        self.profiles = keep_profiles
        self.active_profile = keep_active

    @property
    def active_profile_obj(self) -> Profile:
        return self.profiles.get(self.active_profile, self.profiles["Default"])

    # ------------------------------------------------------------ I/O
    def to_json(self) -> dict:
        data = asdict(self)
        data["profiles"] = {name: prof.to_json() for name, prof in self.profiles.items()}
        return data

    @classmethod
    def from_json(cls, data: dict) -> "Settings":
        settings = cls()
        for key, value in data.items():
            if key == "profiles":
                settings.profiles = {
                    name: Profile.from_json(prof) for name, prof in value.items()
                } or {"Default": Profile(name="Default")}
            elif key in cls.__dataclass_fields__:
                setattr(settings, key, value)
        if settings.active_profile not in settings.profiles:
            settings.active_profile = "Default"
        return settings

    def save(self, path: Path | None = None) -> Path:
        path = path or (user_data_dir() / "settings.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or (user_data_dir() / "settings.json")
        if not path.exists():
            return cls()
        try:
            return cls.from_json(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            # A corrupt settings file must never brick the app (E14):
            # fall back to defaults and keep going.
            return cls()
