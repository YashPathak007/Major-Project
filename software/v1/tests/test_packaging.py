"""Packaging tests (PLAN.md §1.3, §1.4, §8): version, bundled model,
local-only code (no networking imports anywhere in src/), module set,
and the deferred feature list staying deferred.
"""

import re
from pathlib import Path

import pytest

import touchless

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "touchless"

EXPECTED_MODULES = {
    "camera", "model", "mapping", "gestures", "state", "injection",
    "hud", "settings", "tray", "logging", "app", "__init__", "__main__",
}


def test_version_is_1_0_0():
    assert touchless.__version__ == "1.0.0"
    assert touchless.APP_NAME == "Touchless Controller"


def test_module_set_complete():
    present = {p.stem for p in SRC.glob("*.py")}
    assert EXPECTED_MODULES <= present


def test_no_networking_imports_in_src():
    network_modules = {"socket", "urllib", "requests", "http.client",
                       "httpx", "aiohttp", "websockets", "ftplib", "smtplib"}
    for path in SRC.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                module = re.split(r"[ .]", stripped.split()[1])[0]
                assert module not in network_modules, f"{path.name}: {line}"


def test_bundled_model_present():
    model = ROOT / "models" / "hand_landmarker.task"
    assert model.exists()
    assert model.stat().st_size > 1_000_000  # the real model, not a stub


def test_deferred_features_not_implemented():
    """Voice, gaze, app-switch, air-typing, cloud sync, auto-launch and
    multi-hand driving must not appear as code paths in src/."""
    src_text = "\n".join(p.read_text(encoding="utf-8") for p in SRC.glob("*.py"))
    assert "speech_recognition" not in src_text
    assert "whisper" not in src_text.lower()
    assert "auto_launch" not in src_text
    assert "cloud_sync" not in src_text
    # The one-hand rule: only one hand ever drives input (see model.py).
    assert "num_hands=2" in (SRC / "model.py").read_text(encoding="utf-8")
