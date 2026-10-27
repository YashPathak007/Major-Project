# Decisions Log — Major Project

Every step and every decision for this project, dated. Newest first.

## 2026-10-27 — Phase 1 research complete

- **Decision:** Phase 1 (research) is complete with `REPORT.md`. Software and demo come later, by design.
- **Step:** Deep research sweep finished 27 Oct 2026: ~30 queries, ~170 result entries screened, ~60 distinct candidates, 12 papers shortlisted + supporting work + related systems.
- **Step:** Full report written in the required format: Problem Statement → Existing Works (table: Paper / Methodology / Advantages / Disadvantages / Accuracy) → Datasets → Gaps → Proposed Methodology (Data + Method) → Plan → References → Vision → Honesty appendix.
- **Step:** Report + decisions log pushed to this repository (first push; repo was confirmed empty before pushing).

## 2026-10-27 — Scope and direction (from the student's answers)

- **Decision: Project home.** All major-project work lives in this repository (`YashPathak007/Major-Project`), with every step and decision recorded here.
- **Decision: Scope = full control + innovations.** The system must do full Windows control (cursor, clicks, drag, scroll, app launch/switch, typing, settings) plus any good innovations — not a reduced subset.
- **Decision: Research first, software later.** Phase 1 is papers, gaps, and methodology only. No software is built in Phase 1. The demo comes in a later phase.
- **Decision: Quality bar over speed.** The submission deadline (midnight 27 Oct 2026) does not justify random or filler papers. Only authentic, valuable papers are cited; screening is broad (hundreds of candidates considered at index level) and the shortlist is justified.
- **Decision: Datasets must be documented.** Every dataset used is named with size, content, and access/licence notes (licences to be verified on dataset pages before redistribution).
- **Decision: Demo later.** A live demo on the student's Windows laptop (webcam only) comes after the research, in Phase 4.
- **Decision: AR form (assumption, open to correction).** The AR layer is an overlay on the laptop screen itself (the OSO direction). A headset is deferred, not part of this project. If the student corrects this, this line will be updated — not silently changed.
- **Decision: Vision framing.** Stark-inspired, but written and built as professional, real-world engineering, in real human terms and workflows. No science-fiction claims in the report.

## 2026-10-27 — Method decisions (from the literature)

- **Decision: Accuracy honesty rule.** Accuracy is quoted only when the paper itself reports it; otherwise the report says "Not reported". Agent benchmark scores (OSWorld, Windows Agent Arena) are never presented as human-input baselines.
- **Decision: Pipeline shape.** Capture → perception (MediaPipe Hands + gaze) → fusion + smoothing (1€ filter) → intent state machine (lock / point / pending / confirm / act / undo) → native Windows action layer → AR HUD overlay → evaluation on a borrowed OS-task set against a mouse baseline.
- **Decision: Safety and privacy by design.** On-device processing only; no video leaves the laptop by default; landmark-only logs unless a participant consents to video; a visible enabled/disabled indicator; a software kill switch (key + both-palms pose); the system starts DISABLED.
- **Decision: Rest-pose, low-fatigue vocabulary.** The hand rests on the desk; pointing uses small movements + head/gaze; the arm is never required to stay raised (Consumed Endurance, CHI 2014).
- **Decision: Midas-touch guard.** Gaze never clicks alone. Gaze/head points, voice names the action, pinch confirms, open palm cancels. Every consequential action passes through a visible PENDING state with confidence and a one-gesture undo.
- **Decision: New dataset as a contribution.** Because no webcam-video + screen-state + OS-action trace dataset exists for full desktop control, this project will collect one (15–25 scripted Windows tasks × several users × varied lighting, consented, landmark-first).

## 2026-10-27 — Related tracks (not merged into this project)

- **OSO web experience (Holo Viewer OSO):** a browser-based laptop hologram experience with webcam gestures. A parallel track sharing the webcam-control vision; not merged into this repository yet (merge decision pending).
- **OSO Windows Control (native program):** a Python + MediaPipe + pyautogui program for real Windows cursor/click/scroll/app-switch control via webcam. A parallel track; its safety design (starts disabled, ESC kill switch) informs this project's OS action layer.
- **GhostyNav:** deferred to later as a project. Cited in `REPORT.md` only as a related system (verified by direct GitHub repository read 27 Oct 2026), not as peer-reviewed evidence.
- **Stark Vault / Stark UI Demo / classic Holo Viewer:** separate older projects with their own tracks; not part of this major project.
