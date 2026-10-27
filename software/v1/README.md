# Touchless Controller — Version 1 (1.0.0)

Control your Windows 10/11 laptop with one hand in front of the webcam.
No mouse, no touch — just gestures, with a visible confirmation step
before anything clicks.

**This is a real first release, not a demo.** It does the full v1
scope from `../PLAN.md` and nothing beyond it. What is deliberately
*not* in v1: app launching/switching by gesture, air-typing, custom
or multi-hand gestures, voice, gaze, cloud sync, auto-launch,
game/full-screen mode, AI gesture prediction.

## Quick start (Windows 10/11 laptop with a webcam)

1. Install Python 3.11–3.13 from python.org (tick "Add python.exe
   to PATH" during setup).
2. Unzip this package anywhere, then double-click **`run.bat`**.
   The first run creates a `.venv` folder and installs the
   dependencies (needs internet once). Later runs just launch.
3. The app starts **PAUSED** (amber pill, top-right). Nothing moves
   until you deliberately activate it.
4. **Activate:** hold an **open palm** facing the camera for a
   moment. The pill turns teal: TRACKING.
5. **Stop any time:** press **Esc** (the kill-switch), or right-click
   the tray icon and choose Quit. A fist held for a moment also
   pauses (gesture-pause).

## Gestures (dictionary v1.0 — proposed, see note below)

| Gesture | Does | Confirm |
|---|---|---|
| Open palm, held briefly | Activate (the gate) | — |
| Point / move hand | Move the cursor 1:1 | — |
| Quick pinch + release | Click | — |
| Pinch and hold still | Hold-click when the ring completes | Ring around cursor |
| Pinch, hold, then move | Drag (button down on movement, up on release) | — |
| Open palm, move up/down | Scroll (up = scroll up) | — |
| Fist, held briefly | Pause | — |

**Important — elicitation pending:** this dictionary is the plan's
*proposed* set. It is **not yet frozen**: the plan requires an
elicitation study with 5–8 people (you + volunteers) trying the
commands before the set is final. The scroll gesture in particular
is a leading candidate, not a frozen choice — if elicitation shows
low agreement, scroll stays a per-gesture setting you can switch
off and use the mouse wheel instead. Nothing in this build claims
the study has happened.

## The HUD (display-only — it cannot steal focus or clicks)

A small pill, top-right by default, shows the mode (PAUSED /
TRACKING / HAND-LOST / DEGRADED / CALIBRATING / ERROR), the current
gesture, and the hold-progress ring around the cursor. It has no
buttons in daily use, so by construction it can never steal focus
or clicks. A hand-skeleton preview exists for calibration and
diagnosis only and is off by default in daily use. The pill stays
above full-screen content in its corner (it is never suppressed);
the Esc pause key still works from full-screen, and the pill never
names the application under the cursor — it shows the mode only.

Sounds mark every state change (activation, click, drag, pause,
hand lost, error). Sound is never the *only* signal — the pill and
tray icon always show the same state.

## Calibration (recommended on first run)

Right-click the tray icon → **Recalibrate…**, or run the first-run
wizard. You will be shown 5 targets (4 corners + centre): hold a
pinch on each until its ring completes. Keys: **R** redo the current
point, **S** skip to defaults, **C** cancel (keeps your old
profile). Skipping uses the built-in default map for that session
without overwriting your saved profile.

## Settings

Right-click the tray icon → **Settings…** Two levels:

- **Daily:** pause key, quit key, sensitivity, HUD corner / scale /
  opacity, sounds on/off.
- **Advanced:** smoothing preset, dead zone, hold time, camera,
  mirror, drag threshold, scroll step, rest-prompt interval,
  logging, per-gesture on/off, profiles.

Every value is clamped with a plain-language reason (e.g. hold time
below 300 ms "would click without confirming"). **Reset** restores
defaults but keeps your profiles.

## Safety rules (these are guarantees, tested — see TEST_REPORT.md)

- **Gate-closed = zero injections.** While PAUSED, no gesture can
  move or click anything. A direct inject attempt while paused is
  refused and logged as a false-trigger defect.
- **Quit always releases the mouse button first.** Even if a drag
  is in progress, even if the camera pipeline has hung (a watchdog
  force-exits the process after 3 s).
- **Elevated windows are never forced.** If the window under the
  cursor needs higher permission, you see "Can't control this
  window — it needs higher permission. Use your mouse and keyboard
  here." and nothing is injected there.
- **One hand only.** The largest/first hand locks and is never
  switched mid-drag; a second hand is detected and ignored.
- **Mouse and keyboard always work.** They are never disabled.

## Errors (what the pill says, and what to do)

| Pill message | Meaning / fix |
|---|---|
| No camera found | Plug in / enable a webcam, then retry |
| Camera permission denied | Windows Settings → Privacy → Camera → let desktop apps access the camera |
| Camera busy | Close the other app using the camera, then retry |
| No hand found yet… | Move your hand into frame, with light on it |
| Hand lost | Bring the hand back — it resumes automatically |
| Extra hand ignored | (info) a second hand is visible and ignored |
| Light is low | Add light; the app degrades instead of guessing |
| Camera is slow | It steps the resolution down, then degrades |
| Model file missing | Reinstall — `models/hand_landmarker.task` must sit next to `src` |
| Can't control this window… | Use mouse/keyboard for that window (elevated) |
| Something went wrong | Retry from the tray; the app returns to PAUSED, never straight to TRACKING |
| Hand already in use / Settings problem | (rare) restart the app; corrupt settings reset to defaults |

## Privacy

Everything is local. Logs (JSON lines, last 10 sessions) live on
your laptop only; nothing is uploaded, and the code contains no
networking at all. The camera feed is processed in memory and never
saved.

## Files in this package

- `src/touchless/` — the program (11 modules: camera, model,
  mapping, gestures, state, injection, hud, settings, tray,
  logging, app).
- `models/hand_landmarker.task` — the bundled MediaPipe hand model
  (no download on first run).
- `tests/` — the synthetic test suite (run with pytest; see
  TEST_REPORT.md for results).
- `run.bat` / `run.sh` / `build.bat` — launch / rebuild helpers.
- `BUILD_NOTES.md` — every decision and deviation from PLAN.md.
- `TEST_REPORT.md` — real test results and what is NOT yet tested.

## Honest caveats — read before judging

- **Not yet tested on a real Windows laptop or a real webcam.**
  All tests are synthetic (scripted hands, scripted cameras) plus
  headless checks. Real-device proof needs your Windows laptop:
  camera permission flow, actual MediaPipe speed on your CPU, and
  how the gestures feel in your light and room are all unmeasured.
- **Performance budgets are targets, not measurements.** The plan's
  budgets (cursor latency near 0.1 s, FPS/CPU on the weakest
  laptop, hold time, false-trigger rate) are labelled targets to
  validate in pilot testing — this build claims none of them as
  measured.
- **Gesture dictionary not yet frozen** (see above): elicitation
  with 5–8 volunteers is still needed.
- **Command line:** `python -m touchless --help` shows `--camera`,
  `--profile`, `--reset-settings`, `--no-gui` (headless core run).

## Troubleshooting

- *Pill says TRACKING but the cursor doesn't move:* check the
  camera isn't covered and the room is lit; try Recalibrate.
- *Clicks happen when you didn't mean them:* raise the hold time
  in Settings → Advanced, and check the gesture-pause (fist) works
  for you.
- *App won't start / model missing:* re-unzip the package so
  `models/hand_landmarker.task` is present; run `run.bat` again.
- *It can't control a system dialog or admin window:* that is the
  elevated-window rule working as designed — use mouse/keyboard.
