# BUILD_NOTES.md — Touchless Controller v1.0.0

Decisions and deviations from `../PLAN.md`. PLAN.md itself was not
modified. Anything marked "pending" is a validation step for Yash +
volunteers, never something claimed as done.

## Scope: followed exactly (§1)

Built: one hand, activation gate, cursor + click + scroll + drag,
hold-confirm with visible ring, display-only HUD, 4-corner + centre
calibration (redo-one-point, skip-to-defaults), two-level settings
with clamps + reset, Esc kill-switch (rebindable) + tray Quit +
gesture-pause, default PAUSED, local-only logging, mouse/keyboard
fallback, E1–E14 with HUD message + user action + test each.

Not built (deferred per §1.3): gesture app-launch/switch,
air-typing (v1 typing = Enter-confirm after physical typing only;
the controller never types characters), custom/multi-hand gestures,
voice, gaze channels, cloud/profile sync, auto-launch,
game/full-screen mode, AI gesture prediction. A packaging test
asserts the deferred code paths are absent from `src/`.

## Decisions (all inside the plan's latitude)

1. **Scroll gesture — leading candidate implemented, NOT frozen
   (§1.2).** Open-palm vertical move (hand up = scroll up, 30 px
   per step, 3 lines per step, 50 ms min interval). The Wobbrock
   low-agreement fallback is built in: scroll is a per-gesture
   setting — disable it and use the mouse wheel if elicitation
   agreement is low. Elicitation with 5–8 people (MVP commands
   only) is the validation step; it has NOT happened.
2. **Gesture-pause pose — fist held 0.70 s (§1.2).** Proposed pose,
   pending elicitation confirmation like the rest of the dictionary.
3. **Cursor anchor — index fingertip, landmark 8 (§6).** Mirror on
   by default (user's right → cursor right, mirror convention).
4. **Pinch disambiguation — one pinch, three outcomes (§2).**
   Quick release = click on release; hold still until the ring
   completes = hold-click (session consumed, later movement does
   NOT drag); hold + move past the threshold before the ring
   completes = drag (button down on threshold crossing, up on
   release).
5. **Hold time 600 ms, rest prompt 20 min (§6).** Starting values
   from the plan's ranges, NOT pilot results — both are settings
   the pilot tunes.
6. **num_hands=2 in the model (implementation note, NOT a scope
   change).** The model must return 2 hands so the E6 second-hand
   rule can be enforced (second hand detected and ignored). Only
   the primary hand ever drives input — that IS the one-hand rule.
7. **Tray/key Resume = deliberate activation (documented).** The
   gate still blocks every non-deliberate path; Resume is an
   explicit user action, like the G0 pose. PAUSED remains the
   default and the only state the app starts in.
8. **Launch failures go OFF→PAUSED→ERROR.** The §3 table has no
   OFF→ERROR edge, so a failed precondition passes through PAUSED
   (never presented) to ERROR. Retry returns to PAUSED only.
9. **FAILSAFE=False, deliberately.** PyAutoGUI's corner failsafe
   would fire on gestured moves to the top-left corner; this
   program IS the mouse, and its kill-switch is Esc / tray Quit /
   gesture-pause. Documented in `injection.py`.
10. **Settings window lives in `hud.py`.** Structural note only:
    it is a view over the `settings.py` model (the plan's module
    table counts settings as one module; the window is Qt UI, so it
    sits with the other windows).
11. **E2/E3 disambiguation via OpenCV limitation.** OpenCV cannot
    distinguish "busy" from "absent" on its own: E1 = no devices
    probe-able at all; E3 = devices exist but open fails; E2 =
    OpenCV raises a permission error. Each carries its own help
    path in the README.
12. **E7/E8 starting thresholds (§4).** Low light = full-window
    mean brightness < 40, recover > 60. Low FPS = < 12 (step the
    resolution down first, DEGRADED only at the lowest rung),
    recover ≥ 20. Both evaluated on a 5 s cooldown. Starting
    values pending pilot tuning.
13. **Model-complexity ladder step N/A for the Tasks CPU path.**
    The Tasks HandLandmarker has no runtime complexity switch, so
    the degradation ladder is: resolution → 1 hand (already the
    rule) → DEGRADED → pause. Recorded here so the gap is explicit,
    not hidden.
14. **E12 (always-on-top) by construction.** The pill and ring use
    `WindowStaysOnTopHint`; a packaging-level Qt test asserts the
    flags (Frameless + StaysOnTop + Tool + ShowWithoutActivating +
    TransparentForMouseEvents) rather than a runtime probe.
15. **Drag/scroll measured on the UNFILTERED anchor (found by
    testing, 2026-10-28).** The first test run exposed a real
    defect: after a pose change (open palm → pinch), the 1€-filtered
    cursor glides toward the new anchor for several frames, and
    that glide crossed the 12 px drag threshold — turning
    pinch-clicks into false drags and stalling calibration (every
    teleported calibration target glided, so no ring ever
    completed). Fix: `CursorMapper.map_raw()` (mirror + calibration
    only, no filter/dead-zone/sensitivity/clamp) feeds the engine's
    movement decisions (drag displacement, scroll delta); the
    displayed/injected cursor still uses the filtered path.
    Regression-covered by the click test, the drag test, the full
    calibration test, and a dedicated `map_raw` test.
16. **Default-map exact corner (found by testing, 2026-10-28).**
    The default affine matrix computed its offset as
    `(-MIN * width) / span`, which differs from `(width / span) *
    MIN` by 1 ulp, so the min corner mapped to 1.4e-14 instead of
    0.0. Fixed by deriving the offset from the same scale factor.
17. **No PyInstaller exe.** The deliverable is source + `run.bat`
    (venv + install + launch). A frozen exe / installer is
    packaging polish, explicitly later per §1.3.
18. **Settings Reset did not reset scaled sliders (found by
    testing, 2026-10-28).** `_on_reset` called `reset_to_defaults()`
    then `accept()`, and `accept()` reconciled the three scaled
    sliders (sensitivity, HUD scale, HUD opacity) from their stale
    pre-reset positions — so Reset left those three values
    unchanged. Fixed: `_on_reset` now syncs every slider to the
    fresh defaults before `accept()`. Regression-covered by the
    settings-window test.
19. **E12 full-screen decision (plan §4: pick one, document it).**
    PICKED: the HUD pill stays above full-screen content in its
    corner (`WindowStaysOnTopHint`), and is never suppressed. The
    pause key still works from full-screen because the kill-switch
    is a system-wide hotkey, not a HUD button. The HUD never steals
    focus from a full-screen app (ShowWithoutActivating +
    TransparentForMouseEvents, asserted in the HUD tests). Real
    full-screen observation on Windows is still untested (see
    TEST_REPORT.md).
20. **E11 focus-changed behaviour — by construction.** The HUD
    shows only the current mode + gesture chip + transient message;
    no code path ever puts an application name into the HUD, and
    injection always follows whatever window is in the foreground.
    No dedicated test asserts the absence; the HUD tests pin the
    pill's fields (state/chip/hold_progress/transient).

## Test-fixture corrections (tests only, not product changes)

- `dark_frame()` fixture corrected to true black (0) — it was 10,
  above the BLACK_FRAME_MEAN threshold of 8, so the black-frames
  diagnosis could never trigger in tests.
- `make_core()` now opens the test camera — without it every
  `_iterate()` counted a read failure and the core failed E1.
- The "bigger later hand" model test now keeps the locked primary
  in frame — the old version removed the primary, which correctly
  reports HAND-LOST rather than non-displacement.

## Still pending (NOT done — see TEST_REPORT.md)

- Real Windows laptop + real webcam verification (all of §7's
  hardware gates: G-FALSE false-trigger rate, G-SUS, G-FATIGUE,
  the conditions matrix, real FPS/CPU/latency measurement).
- Phase 0 elicitation (5–8 people) to freeze the gesture
  dictionary, including the scroll gesture.
- G-HEUR heuristic evaluation: self-review only in this build
  (checklist in TEST_REPORT.md); a second reviewer has not done it.
