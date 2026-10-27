# TEST_REPORT.md — Touchless Controller v1.0.0

Real results only. Nothing in this file is a projection: every
number below came from a test run, and everything not run is listed
under "Not tested" rather than implied.

## Final result

**83 passed, 0 failed** (full suite, single run, 7.23 s).

Command (from the `v1/` folder, with the test venv active):

```
python -m pytest tests/ -q
```

## Test environment (this run)

- Host: Linux VM (the build machine), Python 3.12.3. The package
  targets Windows 10/11 with Python 3.11–3.13; the code uses no
  3.12-only features, but the suite ran on 3.12, not on Windows
  Python — see "Not tested".
- Test venv (NOT part of the package): mediapipe 1.1.1,
  opencv-python-headless 5.0.0.93 (+ opencv-contrib-python 5.0.0.93,
  pulled in by mediapipe), PyQt6 6.11.0, PyAutoGUI 0.9.54,
  pynput 1.8.2, numpy 2.5.4, pytest 9.1.1.
- Qt tests ran on the offscreen platform (`QT_QPA_PLATFORM=offscreen`
  set by `tests/conftest.py`); no display server was involved.
- System libraries installed on the build VM only to satisfy the
  Qt/mediapipe loaders: libegl1, libgl1, libgles2, libxkbcommon0,
  libdbus-1-3, libfontconfig1. These are test-host prerequisites,
  not package contents (on Windows, PyQt6 bundles Qt).

## Coverage by file (83 tests)

| File | Tests | What it proves |
|---|---|---|
| test_app_core.py | 18 | Journeys + E1–E14 through the core, gates, calibration, lifecycle, hung-pipeline quit |
| test_gestures.py | 11 | Pose rules, gate hold, click vs hold-click vs drag, scroll sign, pause, flicker rejection |
| test_mapping.py | 9 | Default map, mirror direction, affine recovery, degenerate fallback, dead zone, 1€ filter, clamp, raw anchor |
| test_settings.py | 7 | Defaults, clamps + explanations, reset keeps profiles, save/load, corrupt → defaults, no stray slider attributes |
| test_state.py | 6 | Full §3 transition table, ERROR never → TRACKING, sounds, listener payloads |
| test_camera.py | 7 | Bright read, BUSY / ABSENT / PERMISSION / BLACK_FRAMES diagnosis, resolution ladder, FPS |
| test_model.py | 7 | One-hand lock, no auto-promote, never-locked, script cycling, bundled model present, **real MediaPipe load + blank frame → zero hands** |
| test_injection.py | 4 | Passthrough, elevated blocking with E10, mouse-up never blocked, release-all unconditional |
| test_hud.py | 9 | Display-only window flags, tokens, ring, preview, tray mirroring, calibration signals, settings reset, sound distinctness, wizard pages |
| test_packaging.py | 5 | Version 1.0.0, 11-module set, no networking imports, bundled model > 1 MB, deferred features absent |

## Error catalogue E1–E14 — test mapping

| ID | Situation | Test |
|---|---|---|
| E1 | No camera | start_failures (no devices → E1) |
| E2 | Camera permission denied | start_failures (permission error → E2 + help text) |
| E3 | Camera busy | start_failures (devices exist, open fails → E3) |
| E4 | No hand for 10 s | no_hand_guidance (guidance only, never an error state) |
| E5 | Hand lost mid-drag | drag test (button released, HAND_LOST, auto-resume without re-click) |
| E6 | Second hand/person | second_hand_ignored (state unchanged, extra_hands == 1) |
| E7 | Low light | low_light test (DEGRADED on full dark window, recovery on bright) |
| E8 | Low FPS | low_fps test (resolution steps down, DEGRADED only at lowest rung) |
| E9 | Model missing/corrupt | start_failures (factory raises → E9 + expected location); bundled-model test |
| E10 | Elevated target | elevated test (zero backend calls, E10 message, state unchanged) |
| E11 | Focus changed | By construction (HUD shows mode only, never an app name; injection follows foreground). No dedicated absence test — stated, not claimed as tested. |
| E12 | Full-screen app | Decision recorded (pill stays on top, pause key works, no focus theft); window flags asserted in HUD tests. Real full-screen observation on Windows: NOT tested. |
| E13 | Accidental activation | Gate-closed test (zero injections while PAUSED across pinch/idle/fist scripts; direct inject refused + logged as false-trigger defect) |
| E14 | Unusable settings | Clamp tests + corrupt-file test + settings-window reset test (incl. the scaled-slider reset fix) |

## Release gates (§7) — honest status

- **G-GATE — PASS (synthetic).** Zero injections while the gate is
  closed, across all test sessions; any gate-closed injection is
  logged as a false-trigger defect. Real-world false-trigger rate
  (talking/eating/resting hand in front of a real camera) is NOT
  measured — see below.
- **G-DRAG — PASS (synthetic).** Quit during a drag releases the
  button first; the hung-pipeline probe proves the process exits
  (via the 3 s watchdog force-exit) even when inference never
  returns.
- **G-HEUR — SELF-REVIEW ONLY.** Checked against the plan's
  heuristic list by the builder: no silent states (every transition
  changes HUD + sound + tray — asserted in state tests); plain
  -language errors with actions (E1–E14 wording); user control
  (Esc / tray Quit / gesture-pause, all tested); consistency (one
  gesture vocabulary). No independent second reviewer has done it.
- **G-FALSE — NOT TESTED.** Needs real users in front of a real
  camera (false-trigger rate per minute, split by context).
- **G-SUS — NOT TESTED.** Needs 5–10 volunteers and the 10-item
  SUS questionnaire (0–100, not a percent, average ≈ 68).
- **G-FATIGUE — NOT TESTED.** Needs a 10–15 minute real-use block
  with fatigue ratings.
- **Conditions matrix — NOT TESTED.** Light × background ×
  distance × 2 laptops × elevated app × camera-busy, on Windows.
- **Performance budgets — TARGETS, NOT MEASUREMENTS.** Hand→cursor
  latency near 0.1 s, FPS/CPU on the weakest laptop, tuned hold
  time, degradation ladder: none measured on real hardware. The
  suite measures no latency, FPS, or CPU figure, and this report
  claims none.

## Bugs found BY testing (all fixed, regression-covered)

1. **Filter glide → false drags (product defect).** After a pose
   change, the 1€-filtered cursor glided toward the new anchor and
   crossed the 12 px drag threshold — turning pinch-clicks into
   drags and stalling calibration (teleported targets never
   completed a ring). Fixed by measuring drag/scroll on the
   unfiltered anchor (`map_raw`); displayed cursor still filtered.
2. **Default-map 1-ulp corner error.** Min corner mapped to
   1.4e-14 instead of 0.0 (offset recomputed instead of derived
   from the same scale factor). Fixed; exact 0.0 asserted.
3. **Settings Reset left scaled sliders unchanged.** `_on_reset`
   reset defaults then `accept()` reconciled sensitivity / HUD
   scale / HUD opacity from stale slider positions. Fixed by
   syncing sliders to defaults before `accept()`.
4. **Test-fixture corrections (tests only).** Dark-frame fixture
   was 10 (above the black threshold of 8) → true black (0);
   `make_core` now opens the test camera (else every frame counted
   as a read failure → E1); the "bigger later hand" model test now
   keeps the locked primary in frame (removing it correctly
   reports HAND-LOST, not non-displacement).

## Not tested — needs Yash's Windows laptop (stated plainly)

- Real webcam (any camera permission flow on Windows 11, real
  MediaPipe speed on his CPU, gesture feel in his light/room).
- Real Windows behaviour: PyAutoGUI injection into real apps,
  pynput global hotkeys, tray icon/menu, elevated-window check
  (UIPI), UAC/secure-desktop behaviour, full-screen observation,
  multi-monitor/DPI pill placement.
- Qt windows on a real screen (offscreen only here); first-run
  wizard on a real display.
- Gesture accuracy, comfort, fatigue, SUS, false-trigger rate:
  all need the elicitation + pilot volunteers (5–8 for the
  dictionary, 5–10 for SUS/pilot).
- The `run.bat` first-run path (venv creation + pip install on
  Windows) — the script is written but unexecuted on Windows.

## How to re-run

```
# Windows (from the unzipped package folder):
run.bat            # first run installs deps, then launches
# Tests (needs Python + pip install -r requirements.txt -r requirements-dev.txt):
set PYTHONPATH=src
python -m pytest tests/ -q
```
