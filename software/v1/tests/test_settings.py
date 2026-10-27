"""Settings tests — PLAN.md §1.1 item 12, §4 E14."""

import json

from touchless.settings import Settings


def test_defaults():
    settings = Settings()
    assert settings.pause_key == "F9"
    assert settings.quit_key == "Escape"
    assert settings.hold_time_ms == 600
    assert settings.hud_corner == "top-right"
    assert settings.gestures_enabled["scroll"] is True


def test_clamps_with_explanations():
    settings = Settings()
    applied, note = settings.set("hold_time_ms", 0)
    assert applied == 300
    assert note and "without confirming" in note
    applied, note = settings.set("sensitivity", 5.0)
    assert applied == 2.0
    assert note
    applied, note = settings.set("hud_opacity", 0.1)
    assert applied == 0.4
    assert note
    applied, note = settings.set("hold_time_ms", 800)
    assert applied == 800 and note is None  # in-range: no explanation


def test_invalid_corner_and_preset_rejected():
    settings = Settings()
    try:
        settings.set("hud_corner", "centre")
    except ValueError:
        pass
    else:
        raise AssertionError("bad corner must raise")
    try:
        settings.set("smoothing_preset", "turbo")
    except ValueError:
        pass
    else:
        raise AssertionError("bad preset must raise")


def test_reset_restores_defaults_but_keeps_profiles(tmp_path):
    settings = Settings()
    settings.set("hold_time_ms", 1200)
    settings.profiles["Custom"] = settings.profiles["Default"]
    settings.active_profile = "Custom"
    settings.reset_to_defaults()
    assert settings.hold_time_ms == 600
    assert settings.sensitivity == 1.0
    assert "Custom" in settings.profiles  # profiles survive a reset (E14)


def test_save_load_round_trip(tmp_path):
    settings = Settings()
    settings.set("hold_time_ms", 900)
    settings.profiles["Default"].points.top_left = (0.1, 0.2)
    path = tmp_path / "settings.json"
    settings.save(path)
    loaded = Settings.load(path)
    assert loaded.hold_time_ms == 900
    assert loaded.profiles["Default"].points.top_left == (0.1, 0.2)


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = Settings.load(path)
    assert loaded.hold_time_ms == 600  # never bricked by a bad file (E14)


def test_saved_json_has_no_stray_attributes(tmp_path):
    settings = Settings()
    path = tmp_path / "settings.json"
    settings.save(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "sensitivity_x10" not in data
    assert data["hold_time_ms"] == 600
