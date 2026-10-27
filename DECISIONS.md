# Decisions Log — Major Project

Every step and every decision for this project, dated. Newest first.

## 2026-10-27 — Touchless redo (evening): literature review redone around touchless computing, in a professional, table-driven format

- **Decision:** Report restructured in a table-driven format (title + one-line intro; brief problem; existing-works tables; gaps table; innovations list; usage table; pre-requisites table; methodology table; tech-stack table; datasets; next steps; references; vision). Format only — every row, innovation and stage comes from this project's own report, gaps and methodology plus the touchless additions; nothing is copied from a classmate's document except the pre-requisites, which are ma'am's class requirements.
- **Step:** 15 new touchless and gesture-vocabulary papers added (Charade 1993; Johnson 2011; Wachs 2008; Jacob et al. 2013; Gentile 2023; Vogel & Balakrishnan 2005 moved into the touchless section; Walter 2014; reviews Groenewald 2016, Vogiatzidakis & Koutsabasis 2018, Koutsabasis & Vogiatzidakis 2019; survey Rautaray & Agrawal 2015; Wobbrock et al. 2009; Piumsomboon et al. 2013; Vatavu & Wobbrock 2015; Aigner et al. 2012 supporting; Ruiz et al. 2011 supporting-only). Total: 41 numbered papers.
- **Decision:** Re-verdicts applied: 26 earlier papers kept; GhostyNav removed from the papers list (related-system note only); Toyama (1998) demoted to a footnote (secondary sources only, primary source not located).
- **Step:** Professional cleanup: Scholar column and attempt log removed; citation counts omitted (checkable on Google Scholar by title); DOI listed only where primary-confirmed, otherwise omitted with the primary-source link serving as the source; accuracy paper-reported or 'Not reported'.
- **Step:** Gaps table rebuilt in Gap | Source | How our model addresses it form from the project's own 13 gaps (10 original + 3 new: vocabulary without evidence; false activation measured in real use; touchless UI configuration).
- **Step:** Methodology rebuilt as a Stage | Method | Output table from the project's own pipeline, with two touchless additions: a vocabulary-derivation step before the state machine (elicitation study n≈15–20, OS referents, Vatavu & Wobbrock agreement analysis) and a context-gating rule (explicit active state + confirmation channel; face/hand association and gaze direction suppress bystander firing).
- **Step:** Pre-requisites section added (ma'am's class requirements): Python + NumPy + file handling; OpenCV basics; neural networks + LSTM + train/val splits; linear algebra + statistics; usability testing incl. SUS; laptop 8 GB RAM + 720p webcam + good light (GPU optional); 5–10 volunteers.
- **Step:** Updated report + decisions log pushed to this repository; updated PDF rebuilt and uploaded to Drive (new copy).

## 2026-10-27 — Verification pass (evening): every paper checked against its real source

- **Decision:** The report now rests only on papers checked against primary sources. All 18 listed papers (12 shortlist + 6 supporting) were re-checked against publisher pages, arXiv, ACM, IEEE/CVF, or official listings. 15 confirmed as recorded; 3 corrected in the report (Jacob issue 9(3) → 9(2) per ACM DL, with the conflicting PDF header flagged; Molchanov author list and title wording; HaGRID pages 4572–4581 per the CVF PDF).
- **Decision:** Figures that rested only on secondary summaries are no longer quoted as paper-reported (MediaPipe palm AP, WebGazer pixel/degree errors, MPIIGaze 2015 vs 2019 figure, ETH-XGaze baseline, Gaze360 original error). They stay 'not reported' until the full paper text is re-read.
- **Step:** 9 further verified papers added to the review (Vogel & Balakrishnan 2005; Roeber et al. 2003; Typealike 2021; Pavanatto et al. 2021; Jang et al. 2017; PrivacyLens 2024; Saqib et al. 2025; Yang et al. 2023; Pfeuffer et al. 2017), with scope caveats kept explicit (headset papers, mirror attachment, thermal hardware, attack paper as risk evidence).
- **Step:** Google Scholar citation counts could not be retrieved in this pass either (Scholar pages not returned); no Scholar count is claimed anywhere. Only citation metric captured: ACM's for Jacob (693 citations, 7,731 downloads to 10 Oct 2024).
- **Step:** Updated report + decisions log pushed to this repository; updated PDF rebuilt and uploaded to Drive (replacing the earlier copy).

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
- **GhostyNav:** active as its own separate track (TopNotch v1 built 27 Oct 2026 evening; not merged into this project). Cited in `REPORT.md` only as a related system (verified by direct GitHub repository read 27 Oct 2026), not as peer-reviewed evidence.
- **Stark Vault / Stark UI Demo / classic Holo Viewer:** separate older projects with their own tracks; not part of this major project.
