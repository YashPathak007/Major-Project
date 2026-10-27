# Major Project — Webcam-Based AR Control of a Windows Computer

**Student:** Yash Pathak
**Programme:** BCA Major Project
**Repository:** https://github.com/YashPathak007/Major-Project

## Vision

Sit down at an ordinary Windows laptop, and use the whole computer — cursor, clicks, apps, typing, settings — by being watched by its webcam, with a live AR overlay on the screen showing what the system understands. No headset. No extra hardware. Stark-inspired, built as real engineering.

## Status

- **Phase 1 — Research: COMPLETE (27 Oct 2026), redone the same evening with a touchless-computing expansion in a table-driven format.** See `REPORT.md` — the full research report (brief Problem Statement, literature review of 41 numbered papers + Toyama footnote + GhostyNav related-system note, gaps table, innovations, usage, pre-requisites, methodology table, tech-stack table, datasets, next steps, references, vision).
- **Phase 2 — Prototype: Version 1 BUILT (28 Oct 2026).** Touchless controller v1.0.0 — one hand, activation gate, cursor/click/scroll/drag, hold-confirm, display-only HUD, calibration, settings, kill-switch; starts PAUSED. See `software/v1/`. Not yet tested on a real Windows laptop/webcam; gesture dictionary not frozen (elicitation with 5–8 volunteers still to come).
- **Phase 3 — Evaluation.** Full Windows task set, baselines, robustness matrix, fatigue study, HUD-on/off comparison, false-activation experiment.
- **Phase 4 — Demo + final submission.** Live demo on the student's Windows laptop (webcam only), final report with measured results, public trace dataset + reporting template.

## Contents

- `REPORT.md` — the full Phase 1 research report (the submission document).
- `DECISIONS.md` — every step and every decision, dated, so the project's direction is always traceable.
- `software/v1/` — Version 1 of the touchless controller software (source, tests, docs; the MediaPipe hand-model binary is not in the repo — see `software/v1/models/README.md`).

## Key finding (Phase 1)

No prior system does it all from one laptop webcam on a consumer CPU: cursor + click/drag/scroll + app launch/switch + typing + settings across arbitrary Windows apps, with a live AR/HUD overlay, evaluated as a full OS task suite. The pieces exist separately; the integration — plus on-device privacy, fatigue-aware design, and a comparable OS-task evaluation — is the genuine contribution.

## Scope decisions (see DECISIONS.md for the full log)

- Full Windows control, plus any good innovations — not a subset.
- Research first, software later. Demo comes after the research.
- One built-in laptop webcam; consumer CPU; no headset, no depth sensor, no extra hardware.
- Datasets are documented; a new webcam-OS trace dataset is a planned contribution (none exists today).
