# Major Project — Research Report
## Webcam-Based AR Control of a Windows Computer

**Author:** Yash Pathak
**Programme:** BCA Major Project
**Phase:** Phase 1 — Research (software and demo come later)
**Date:** 27 October 2026
**Repository:** https://github.com/YashPathak007/Major-Project
**Status:** Research complete. This report is the submission document for Phase 1.

> **Vision, in one line:** Sit down at an ordinary Windows laptop, and use the whole computer — cursor, clicks, apps, typing, settings — by being watched by its webcam, with a live AR overlay on the screen showing what the system understands. No headset. No extra hardware. Stark-inspired, built as real engineering.

---

## 1. Problem Statement

### The problem

Today, using a computer still means touching it: a mouse, a keyboard, a trackpad. That is fine for most people, most of the time — but it leaves out real situations. Hands can be busy, dirty, injured, or absent. A person with limited mobility may not be able to use a mouse at all. A person cooking, repairing, or presenting cannot keep returning to the keyboard. And every science-fiction interface people admire — the ones where a person simply moves, points, and speaks while the computer follows — remains fiction, because no ordinary laptop can do it.

The problem this project solves is: **can one ordinary laptop webcam, watching the user, give full control of a Windows computer, with an AR overlay on the screen that shows what the system sees and intends — running on a consumer CPU, with no headset, no depth sensor, and no extra hardware?**

### What "full control" means here

Full control is not one demo trick. It is the complete everyday workflow, in one session:

- Move the cursor precisely to any target, large or small.
- Click, double-click, drag, and scroll.
- Launch any application, switch between windows, and manage files.
- Type into any application, including shortcuts (Ctrl+C, Alt+Tab) and passwords.
- Change system settings (volume, Wi-Fi, brightness, dark mode).
- Do all of this through an AR/HUD overlay that shows the current mode, the focused window, the pending action, and its confidence — and lets the user cancel with one gesture.

### Why now

Three things changed recently enough to make this realistic for a student project:

1. **On-device hand tracking works.** MediaPipe Hands tracks 21 hand landmarks from a single RGB camera in real time on weak hardware, open source.
2. **Webcam gaze estimation works.** Learned models estimate where a person looks from an ordinary webcam, with no infrared hardware.
3. **Full-OS benchmarks exist.** OSWorld and Windows Agent Arena define "full computer control" as hundreds of scripted, checkable Windows tasks — so a human-input system can finally be measured the same way.

### Who it is for

- Everyday laptop users who want a touch-free way to work.
- People with limited mobility, for whom a camera is far easier than a mouse.
- People whose hands are busy (presenters, makers, cooks, technicians).
- Anyone who has watched a Stark-style interface and asked: why can my laptop not do that?

### Constraints (what this project will NOT assume)

- One built-in laptop webcam. No depth camera, no Leap Motion, no IR eye tracker, no headset.
- A consumer laptop CPU. No high-end GPU required.
- Arbitrary Windows applications — not one specially-built demo app.
- Real rooms: changing light, glasses, other people in frame, long sessions.

### What success looks like

A working system, evaluated on a borrowed Windows task set (in the style of OSWorld / Windows Agent Arena) against a mouse-and-keyboard baseline, reporting task success, time, errors, false activations, CPU use, lighting robustness, and fatigue — plus a small public dataset of webcam-video + screen-state + OS-action traces, because none exists today.

---

## 2. Existing Works — Literature Review

### How papers were found and chosen

About 30 web-index queries were run across seven areas: hand gesture / MediaPipe Hands; gaze, eye-tracking and head pose; AR overlays for desktop interaction; camera-based virtual keyboards and app control; multimodal control; accessibility camera control; and latency, robustness, fatigue and CPU-only performance. Queries also covered datasets (HaGRID, Jester, nvGesture, EgoGesture, SHREC, MPIIGaze, GazeCapture, ETH-XGaze, Gaze360) and full-OS benchmarks (OSWorld, Windows Agent Arena).

Roughly 170 search-result entries were seen; after de-duplication about 60 distinct papers, datasets and systems were candidates. The 12-paper shortlist below was chosen by these rules:

- **Include first:** peer-reviewed work (CVPR / ICCV / ECCV / CHI / UIST / IEEE / ACM venues, or a widely adopted open system with a paper, e.g. MediaPipe Hands) that *demonstrates a control loop* — a cursor, a click, a typed character, a completed app/OS task — not classification accuracy alone.
- **Prefer:** a single RGB webcam (no depth sensor, Leap Motion, IR eye tracker or headset required), because that is this project's hardware constraint.
- **Exclude as filler:** generic "virtual mouse" student demos and blog posts with no user study, no dataset and no reproducible evaluation; depth-only gesture classifiers; commercial overlay products with no technical paper.
- **Accuracy rule:** a number is quoted only when the paper (or a source quoting it) reports it. Otherwise the table says **Not reported** — never an invented percentage. Where sources report the same result in different units (WebGazer in degrees vs pixels), both are flagged rather than harmonised by guesswork.
- **Citation counts:** live Google Scholar counts were not retrieved in this review session, so no current Scholar count is claimed for any paper. Influence is described qualitatively (venue, adoption as a baseline/dataset, reuse in later systems). Any count added later must be re-checked on Scholar on the day of writing and dated.

### Comparison table (the photo's format)

| Paper | Methodology | Advantages | Disadvantages | Accuracy |
|---|---|---|---|---|
| MediaPipe Hands — Zhang et al. (2020, arXiv / Google Research) | Palm detector → 21-landmark (2.5D) hand model; detector re-run only when tracking confidence drops | Single RGB camera, on-device, open source, runs on mobile/desktop; the de-facto building block for webcam hand control | Landmark quality degrades with occlusion, fast motion, poor light; 2.5D depth is relative to wrist, not metric; no gesture vocabulary or OS action layer itself | Not reported as a % (paper reports landmark error and phone inference time: Full model 16.1 ms on Pixel 3, 11.1 ms on Samsung S20, 5.3 ms on iPhone 11) |
| Online Detection and Classification of Dynamic Hand Gestures with Recurrent 3D CNNs — Molchanov et al. (2016, CVPR) | Recurrent 3D CNN over RGB + depth + flow (+ IR in full system); online detection + classification on nvGesture | Dynamic (not just static-pose) gestures; designed for real-world, always-on detection; near-human on its benchmark | Requires depth/IR sensor in the full system — not a plain webcam; car/interior setting, not a desktop; fixed gesture set, no OS task evaluation | 83.8% (all modalities); human accuracy 88.4% on same data |
| The Camera Mouse — Betke, Gips & Fleming (2002, IEEE Trans. Neural Syst. Rehabil. Eng.) | Template-correlation visual tracking of a chosen body feature (nose tip, finger, etc.) from a standard camera; feature motion → mouse pointer | The original proof that a plain camera + room light can replace a mouse; tested with people with severe disabilities, not only able-bodied students; free, no special hardware | Pointer only — clicking needs dwell/switch add-ons; template tracking is fragile vs modern learned trackers; small, old studies; no app-launching, typing or settings layer | Not reported as a classifier %; early study: 9 of 12 people with severe cerebral palsy / brain injury succeeded (spelling, running software, web) |
| The Use of Eye Movements in Human-Computer Interaction Techniques — Jacob (1991, ACM Trans. Inf. Syst.) | Eye-tracker-driven techniques (object selection, scrolling, etc.) analysed as a dialogue; identified the Midas Touch problem | Foundational design lesson for any gaze system: eyes are always "on", so looking must not equal clicking; still the correct framing for a gaze+gesture hybrid | Used expensive 1990s eye trackers, not a webcam; qualitative/technique paper, no modern accuracy benchmark; dwell-time fix it popularised is slow | Not reported |
| WebGazer — Papoutsaki et al. (2016, IJCAI) | Browser JS: face/eye detection + pupil features → ridge regression to screen coordinates; self-calibrates continuously by assuming gaze ≈ click/mouse position during interaction | Runs on any laptop webcam in a browser, no install, no IR hardware; scalable to remote studies; the only widely reused open webcam-gaze baseline | Coarse: good for regions/areas of interest, not pixel-precise small targets; needs interaction data to self-calibrate; accuracy collapses with head movement and poor calibration | 4.17° visual angle in lab study (as cited in later papers); other summaries give 130–257 px mean error depending on model — units differ, do not compare directly |
| Eye Tracking for Everyone (GazeCapture / iTracker) — Krafka et al. (2016, CVPR) | CNN (iTracker) trained on crowdsourced phone/tablet front-camera data; face + eye crops → screen point | First large-scale webcam-class gaze dataset; proved learned appearance-based gaze can run in real time on commodity devices; features generalise to other datasets | Phone/tablet geometry, not a laptop-at-desk geometry; error in centimetres is still too large for small desktop UI targets without magnification/confirmation; dataset access behind registration | 1.71 cm (phone) / 2.53 cm (tablet) uncalibrated; 1.34 cm / 2.12 cm with calibration; 10–15 fps on a contemporary mobile device |
| Appearance-Based Gaze Estimation in the Wild (MPIIGaze) — Zhang, Sugano, Fritz & Bulling (2015, CVPR) | Multimodal CNN: eye images + head-pose → 3D gaze; dataset collected during everyday laptop use over 3+ months | First in-the-wild (not lab) gaze dataset for laptops — the closest gaze dataset to this project's actual setting; cross-dataset evaluation exposed dataset bias | Only 15 participants; gaze estimation, not a control system (no click, no typing, no OS loop); no single % accuracy quoted in sources checked | Not reported (as a % in sources checked; paper's contribution is cross-dataset comparison, not one headline number) |
| ETH-XGaze — Zhang et al. (2020, ECCV) | 18-DSLR rig + calibrated gaze targets; over 1M high-resolution images under extreme head pose / gaze variation; standard protocol + metric | Largest head-pose/gaze variation of any gaze dataset; standardised protocol is exactly what the field lacked for comparability | Lab rig, not a laptop webcam; trains gaze estimation, not interaction; extreme poses help robustness research but do not solve the small-target desktop pointing problem | Not reported as a single % (dataset/benchmark paper) |
| OSWorld — Xie et al. (2024, NeurIPS) | Real Ubuntu/Windows/macOS VMs + 369 scripted real-world tasks (apps, files, web, multi-app); execution-based success/fail scoring for multimodal agents | The first credible full-OS task benchmark: it defines what "full computer control" means measurably (launch, edit, save, configure, multi-app workflows) | Benchmarks AI agents (VLM planners), not human gesture/gaze input — its action space is screenshots + synthetic clicks, not webcam signals; no latency, fatigue or robustness-to-lighting dimension | Best agent under 12.2% at publication; humans 72.4% on the same 369 tasks (agent scores, NOT human-camera baselines) |
| Windows Agent Arena — Bonatti et al. (2024 arXiv / 2025, ICML, PMLR 267) | Real Windows 11 environment, 150+ tasks, parallelisable evaluation; new agent "Navi" as baseline | Windows-specific (this project's OS), faster to run in full than OSWorld (reported ~20 min parallelised); shows even strong multimodal agents fail most real Windows tasks | Same caveat as OSWorld: agent benchmark, not a human-input benchmark; success is end-state only, so it hides how clumsy or slow the interaction was | Navi 19.5% vs human 74.5% (agent scores, NOT human-camera baselines) |
| Consumed Endurance — Hincapié-Ramos et al. (2014, CHI) | Biomechanical + subjective model of shoulder/arm fatigue ("gorilla arm") for mid-air selection; compares click, dwell, swipe, second-hand methods | The only shortlist paper that quantifies why always-raised-hand control fails over time; directly constrains gesture design (rest poses, small planes, low-movement confirmation) | Mid-air large-display setting, not laptop-desk; small lab sample; a metric, not a complete system — it tells you what to avoid, not how to build the controller | Not reported as accuracy; fatigue result: click lowest consumed endurance (8.18%) and lowest Borg CR10 (1.19); swipe worst |
| WindowSpace — Marguet et al. (2025, Proc. ACM Hum.-Comput. Interact.) | Web-based XR window manager: native 2D desktop windows streamed (WebRTC) into immersive 3D space; three cursor-transfer techniques compared (EtherXR off-screen cursor, Face&Jump head pointer, BallisticXR trajectory extension) | The closest peer-reviewed analogue to an "AR overlay for desktop work": it studies the exact hard problem — moving a cursor between windows without losing it — and finds head-only pointing is slow/inaccurate without gaze help | Requires an XR headset, not a flat-screen HUD; still uses mouse+keyboard as base input, so it is an overlay around the desktop, not webcam control of the desktop; very recent (2025), so no replication base yet | Not reported numerically in the abstract (relative result only: EtherXR slightly best overall, BallisticXR more accurate, Face&Jump slower and less accurate) |

### Supporting papers (required by the categories, not in the 12)

- **Bolt, "Put-That-There" (1980, SIGGRAPH).** The first speech + deictic gesture system ("put that [point] there [point]"). Lesson: multimodality works when each channel does what it is good at — speech names the action, gesture names the target — rather than duplicating the same command in two channels. This project copies that division (e.g. voice: "open"; gesture: which app tile; gaze: where; pinch: confirm) instead of treating voice as a second mouse.
- **Casiez, Roussel & Vogel, "1€ Filter" (2012, CHI).** A speed-adaptive low-pass filter: strong smoothing at low speed (kills jitter), low lag at high speed. Directly reusable in a webcam cursor pipeline; two parameters, almost no CPU cost. Any webcam cursor that jitters without citing or implementing this (or a Kalman equivalent) has missed the obvious prior art.
- **Toyama, "Look, Ma — No Hands!" (1998).** Early proof that face-normal → screen point + Kalman smoothing can drive a cursor from a desktop camera on a 266 MHz PC — a useful historical CPU-only precedent.
- **Yin et al., "CamK" (2016, IEEE INFOCOM).** Camera watches typing on a printed paper keyboard; reported over 95% keystroke localisation, 4.8% false-positive keystrokes, 1.25× typing speedup vs on-screen keyboard for regular text. Relevance: the strongest peer-reviewed camera-typing result found — but it needs a printed layout and a phone camera angle, so it does not solve on-screen desktop typing. Desktop typing in prior work is otherwise dominated by slow dwell/on-screen keyboards in accessibility tools (Camera Mouse / eViacam lineage), which is why typing is a gap, not a solved subproblem.
- **Gaze360 (Kellnhofer et al., 2019, ICCV).** Treated as a dataset below, not a shortlist row, to avoid double-counting gaze-estimation papers; its 238-subject, indoor+outdoor, 1–3 m distance data is the best "unconstrained" gaze reference after ETH-XGaze.

### Related systems (not papers — practical context)

- **GhostyNav (TheCidSama/GhostyNav, GitHub, MIT).** A Dynamic Island-style notch overlay for Windows 10/11 (WPF/.NET) with a pixel-ghost voice assistant, control centre, widgets, stats, clipboard history and app launcher, in ~24 MB of RAM. Transparency note: this project verified GhostyNav directly from its public GitHub repository (description and README read 27 Oct 2026); an independent web search in this review could not confirm it, so it is cited here as a related system on the basis of that repository read — not as peer-reviewed evidence, and not with claims beyond what its README states. Its value here is as a practical reference for Windows overlay mechanics (top-most, non-activating, glanceable) — and as a warning: its "stealth" framing is an academic-integrity liability a university project must explicitly distance itself from.
- **Notch — Dynamic Island for Windows 11 (Jaswanth1902/Notch, GitHub).** An open-source, top-of-screen ambient HUD (60 fps spring physics, claimed under 40 MB RAM, zero focus theft) surfacing background-agent telemetry from JSON spool files. Closest honest analogue to a notch HUD: a small, non-activating, always-visible strip reporting system state without taking focus. This project's HUD should copy Notch's constraints (no focus theft, tiny CPU/RAM, glanceable state) and replace agent telemetry with controller state (mode, tracked hand/face, pending action, confidence).
- **Unhindered and Hands-Free Control.** Current accessibility products that already do much of this mission from a webcam: head → pointer, face/hand/voice → click, type, scroll, on-screen keyboard, fully offline (Hands-Free Control claims ~16 ms head tracking). Implication: this project cannot claim novelty for "webcam moves the mouse" — it must beat or differentiate on full-OS task coverage, evaluation, fatigue, privacy, or the AR HUD, and should benchmark against one of these (or eViacam/Camera Mouse) rather than only against a physical mouse.
- **eViacam / Enable Viacam (open source, Windows/Linux, GPL).** Head-movement mouse emulator with dwell/gesture clicking and an on-screen control bar; long-lived accessibility software, still the most credible free baseline for head-pose control.
- **Ghosty AI (ghosty-ai.com).** A Windows screen overlay that screenshots, transcribes audio and drafts answers, marketed as "stealth"/invisible to screen sharing, with hotkeys and automated typing. It proves Windows overlay mechanics are productised — but it is an AI answer assistant, not a camera controller, and its stealth framing raises academic-integrity questions a student project should explicitly distance itself from.

---

## Datasets

| Dataset / benchmark | Size & content | Best use for this project | Licence / access notes (verify on the dataset page before use) |
|---|---|---|---|
| HaGRID (Kapitanov et al., WACV 2024) | 554,800 FullHD images, 18 gestures + "no gesture", 37,583 subjects, 0.5–4 m, varied natural light, bounding boxes | Static-gesture pretraining / validation for a device-control vocabulary | Public via GitHub (hukenovs/hagrid); licence not stated in sources checked — check repo before redistributing |
| HaGRIDv2 (2024/2025) | 1,086,158 images, 33+1 classes, 65,977 subjects, boxes + keypoints | Same, with a larger vocabulary and dynamic-gesture support | Public via the same project; licence not verified here |
| 20BN-Jester (Materzynska et al., 2019) | 148,092 webcam videos, 27 classes (25 gestures + "no gesture" + "doing other things"), 1,376 actors, ~3 s clips; split 118,562 / 14,787 / 14,743 | Dynamic-gesture training; its two "negative" classes are the right way to teach a live system not to fire | Widely mirrored for research; original TwentyBN terms apply — check before commercial use |
| nvGesture (Molchanov et al., 2016) | 1,532 RGB-depth videos, 20 subjects, 25 classes, car interior, dim/bright light | Dynamic-gesture baseline; contrast case showing what depth buys (and what a webcam-only system gives up) | Research-only availability noted in secondary sources; not a webcam dataset |
| EgoGesture (Zhang et al., ICCV 2017 lineage) | 2,081 RGB-D videos, 24,161 gesture samples, 2,953,224 frames, 50 subjects, 83 classes, 6 indoor/outdoor scenes incl. walking + drastic sunlight | Continuous-gesture detection (segmented + unsegmented testbed) | Project page: nlpr.ia.ac.cn/iva/yfzhang/datasets/egogesture.html; access terms on that page |
| SHREC / DHG-14/28 (2017) | 2,800 depth+pose sequences, 28 subjects, 14 or 28 classes | Skeleton-based dynamic gesture comparison | Benchmark data; check challenge page for terms |
| MPIIGaze (2015) | 213,659 images, 15 laptop users, everyday use over 3+ months | Laptop-gaze fine-tuning / in-the-wild robustness test | Research dataset via MPI; small subject count limits generalisation claims |
| GazeCapture (Krafka et al., 2016) | ~2.5M frames, over 1,450 people, phone/tablet front cameras, varied backgrounds/poses/light | Large-scale gaze pretraining; held-out-user evaluation | A secondary thesis source notes raw download is behind registration — plan access time accordingly |
| ETH-XGaze (2020) | Over 1M high-resolution images, 110 participants, 18 DSLR cameras, extreme head pose/gaze, standard protocol | Head-pose robustness benchmark; pretraining reference | Benchmark site: ait.ethz.ch/xgaze; lab-collected, not reproducible on a laptop |
| Gaze360 (Kellnhofer et al., 2019) | 238 subjects, indoor+outdoor, 129k train / 17k val / 26k test images, 1–3 m camera distance, full yaw range | Unconstrained gaze evaluation (distance + pose variation) | Public dataset site named in the paper (gaze360.csail.mit.edu); check current hosting |
| RT-GENE (Fischer et al., ECCV 2018) | ~92k images, 13 subjects (as summarised in later papers), 80–280 cm distance, raw + normalised versions | Gaze at a distance (closer to a desk than phone datasets, farther than a webcam's ideal) | Check project page for terms |
| EyeDiap (2014) | Video from 16 subjects, screen-target + floating-target sessions, RGB-D (Kinect) | Screen-target gaze (the desktop-relevant subset) | Small; lab-collected |
| OSWorld (2024) | 369 real OS tasks, Ubuntu/Windows/macOS, setup + execution-based evaluation scripts | Task taxonomy + scoring template for this project's own human-input evaluation (do not reuse its agent scores) | Open-source benchmark: os-world.github.io |
| Windows Agent Arena (2024/2025) | 150+ Windows tasks across 11 apps, PyAutoGUI-style action space (click, drag, scroll, type, hotkey) | Windows task checklist + action vocabulary for this project's test suite | Open source: github.com/microsoft/WindowsAgentArena |

**Flag — no standard benchmark exists for full OS-level control by webcam input.** OSWorld and Windows Agent Arena are the closest benchmarks, but both score autonomous agents acting on screenshots, not humans acting through a camera. There is no published dataset of webcam video + screen state + OS action traces for full desktop control, and no agreed metric that jointly scores task success, time, errors, fatigue and robustness (lighting, occlusion, second person in frame). A project that creates even a small version of this — e.g. 15–25 scripted Windows tasks × several users × varied lighting, with video, landmarks, actions and success/time/error logs — would itself be a contribution, provided consent and on-device handling are documented.

---

## Gaps in prior research (what this project will fill)

1. **Single-app demos vs full OS control (the central gap).** Almost every webcam-control demo controls one thing: a media player, a presentation, a drawing canvas, or a browser page. Camera Mouse moves a pointer; WebGazer estimates gaze; MediaPipe Hands tracks a hand. None of them, alone or combined in the literature, demonstrates launching an arbitrary app, switching windows, navigating a file dialog, changing a system setting, and typing into a third app in one session — the exact workflow OSWorld/WAA formalise for agents but no human-input paper formalises for camera users.
2. **Consumer-CPU real-time performance, honestly measured.** MediaPipe Hands proves phone-GPU real-time (Full model ~5–16 ms on phones in 2020), but a student laptop has a shared CPU, a webcam, a compositor, an overlay renderer and the target app competing for the same cores. Most virtual-mouse write-ups quote "real-time" with no end-to-end latency budget (capture → inference → smoothing → OS injection → screen feedback) and no CPU-% / frame-drop report at, say, 720p with face + hands + gaze running together. Running three tracking graphs at once is a different system from running one.
3. **Robustness to real rooms and lighting.** MPIIGaze and Gaze360 exist precisely because lab accuracy collapses in the wild (backlight from a window, low evening light, glasses, skin-tone and age variation, occlusion when a hand covers the face or vice versa). HaGRID's 37k scenes and Jester's cluttered backgrounds are the gesture equivalents. Yet control papers rarely report accuracy by lighting condition (one pattern found: a gesture+voice system reporting 90% overall but 60% in low light — showing how large the drop is). No shortlist paper reports a lighting × occlusion × distance matrix for a full control loop.
4. **Multi-person scenes and attention ownership.** A laptop webcam in a shared room, classroom or office sees other people, passers-by and video-call participants. No shortlist system addresses "which person is the user?" robustly — identity persistence, face/hand association across frames, or a deliberate lock/unlock gesture. A system that follows the wrong hand will click the wrong thing; this is a safety issue, not just an accuracy one.
5. **Fatigue over long use.** Consumed Endurance (CHI 2014) quantifies gorilla-arm for mid-air interaction, but camera-control evaluations are typically minutes long, single-session, and able-bodied. There is no longitudinal (days/weeks) study of a webcam desktop controller: no data on rest-pose design, session length before errors rise, or whether users actually keep using it after the novelty demo. An evaluation that only reports a 5-minute demo accuracy will reproduce this gap.
6. **The Midas Touch + confirmation problem, unsolved in practice.** Jacob (1991) named it; dwell clicking mitigates it by being slow; pinch/blink/voice confirmation mitigates it by adding a second channel that itself misfires. No paper gives a measured false-activation rate in a real desktop session (not a gesture test set) for a complete system, nor a principled comparison of dwell vs pinch vs blink vs voice confirmation on the same tasks. This is the single most important experiment this project can run.
7. **Typing is the weakest link.** Camera typing is either a slow dwell/on-screen keyboard (accessibility lineage: Camera Mouse, eViacam) or a printed-paper keyboard (CamK, over 95% localisation but a different device). No shortlist system types at anything approaching keyboard speed into arbitrary apps, handles modifiers/shortcuts (Ctrl+C, Alt+Tab), or recovers gracefully from a mis-typed character without breaking flow. Voice dictation helps for prose but not for passwords, code or shortcuts — and voice is unusable in shared/noisy rooms, which the multimodal literature rarely evaluates.
8. **Privacy of an always-on camera.** A full-control system must watch continuously to know when the user wants control — which means it watches when they do not. Prior control papers almost never discuss this: no on-device-only guarantee, no indicator discipline, no "camera off" state that is actually off, no handling of bystanders, screen content in the background, or what happens to landmark/video logs. Users adapt by changing behaviour or avoiding the room — an adoption risk this project addresses by design (local processing only, no video storage by default, visible on/off + lock gesture, landmark-only logging with consent).
9. **Evaluation comparability.** Gesture papers use different vocabularies, splits, lighting and metrics (classification % vs task time vs Fitts' throughput vs cm/degree error); gaze papers use cm, degrees and pixels interchangeably (see WebGazer). Without a shared task set, a shared negative class ("doing other things", Jester's lesson) and a shared reporting template (success, time, errors, false activations, CPU, lighting), two projects cannot be compared — and neither can be compared to a mouse/keyboard baseline, which is the comparison that actually matters for a claim of "usable".
10. **AR overlay as interaction, not decoration.** WindowSpace shows overlay/window management is a research problem (cursor transfer, focus, occlusion), but flat-screen HUD work is mostly cosmetic: draw a skeleton, draw a gesture label. No shortlist paper evaluates whether an overlay improves task performance — e.g. showing focus window, pending action + confidence, a cancel affordance, and a magnified target for gaze — versus the same controller with the overlay off. A "Stark/JARVIS-style" HUD that only looks futuristic, without a measured benefit and without solving focus theft / click-through on Windows (top-most, transparent, non-activating windows), is presentation, not engineering.

**Genuine innovations this project claims (derived from the gaps, not from prior work):** (i) a unified gesture+gaze+voice state machine with an explicit lock, confirm and cancel path, evaluated on a borrowed OSWorld/WAA-style Windows task set with a mouse baseline; (ii) a rest-pose, low-fatigue vocabulary (hand on desk, micro-gestures + head/gaze for pointing, pinch only to confirm); (iii) a confidence-aware AR HUD that shows what the system thinks you meant before it acts, with one-gesture undo; (iv) on-device-only processing with landmark-only logs and a physical-software kill switch; (v) a small, consented, public webcam-OS-control trace dataset + reporting template (success/time/errors/false-activations/CPU/lighting) so the next student can compare.

---

## 3. Proposed Methodology

### Data

**Datasets used (pretraining, validation, benchmarking):**

- **Gestures:** HaGRID (554,800 images, 18+1 classes) and HaGRIDv2 (1,086,158 images, 33+1 classes) for static-gesture vocabulary; 20BN-Jester (148,092 videos, 27 classes including two negative classes) for dynamic gestures and for teaching the live system *not* to fire; EgoGesture (24,161 samples, 83 classes) for continuous detection; nvGesture as a depth-based contrast case.
- **Gaze:** MPIIGaze (213,659 images, 15 laptop users, in-the-wild) for laptop-gaze fine-tuning; GazeCapture (~2.5M frames, 1,450+ people) for large-scale pretraining with held-out-user evaluation; ETH-XGaze (1M+ images, 110 people) as a head-pose robustness reference; Gaze360 (238 subjects) for unconstrained evaluation.
- **Benchmarks (task design, not scores):** OSWorld (369 tasks) for the full-OS task taxonomy and execution-based scoring template; Windows Agent Arena (150+ Windows tasks) for the Windows task checklist and action vocabulary (click, drag, scroll, type, hotkey). Agent scores from these benchmarks are NOT baselines for a human-input system and are never presented as such.

**New dataset to collect (a contribution in itself):**

Because no webcam-video + screen-state + OS-action trace dataset exists for full desktop control, this project collects one: 15–25 scripted Windows tasks (launch, file, browser, office, settings, multi-app) × several users × varied lighting (bright, evening, backlit) and conditions (glasses, second person briefly in frame). Each session records: webcam video (consented, stored only with explicit permission; otherwise landmarks only), hand/face landmarks, recognised gestures, OS actions issued, task success, time, errors, false activations, CPU use, and a short fatigue rating. Consent forms, on-device handling, and a landmark-only default are part of the methodology, not an afterthought.

**Data handling rules:** on-device processing only; no video leaves the laptop by default; no video storage without explicit consent; bystanders are not recorded as subjects (sessions stop or blur non-user faces); all logs are landmark + action records unless the participant opts into video.

### Method (the pipeline)

The system is a pipeline of six stages, each with a named prior-art anchor and a measurable output:

1. **Capture.** One laptop webcam (720p target) + microphone (voice optional, not required). Output: frames + audio, timestamped. Honest budget: capture latency is part of the end-to-end number, not hidden.
2. **Perception.** MediaPipe Hands (21 landmarks, 2.5D) for hands; appearance-based gaze estimation (WebGazer-style ridge regression for the browser layer, MPIIGaze/GazeCapture-pretrained model for the native layer) for gaze; head pose from face landmarks. All on-device, CPU-targeted. Output: landmarks + gaze point + head pose per frame, with confidence.
3. **Fusion + smoothing.** Landmark/gaze streams are fused and smoothed before any action: 1€ filter (Casiez et al., 2012) for cursor stability (strong smoothing at low speed, low lag at high speed), a short temporal window for dynamic gestures (Molchanov et al.'s lesson: explicit background/"no gesture" handling, Jester's negative classes), and a Kalman-style fallback. Output: a stable, low-jitter pointer + a gesture/gaze event stream that does not fire on noise.
4. **Intent state machine (the core).** A single explicit state machine, not a pile of if-statements: states LOCKED → POINTING → PENDING (action + confidence shown on the HUD) → CONFIRMED → ACTING → UNDO-AVAILABLE. Division of labour (Bolt, 1980): gaze/head points, voice names the action ("open", "search"), pinch confirms, open-palm cancels, a lock gesture (or key) locks/unlocks control. Midas-touch guards: gaze never clicks alone; dwell is a fallback, not the default; every consequential action (open, type, delete, settings change) passes through PENDING with a visible confidence and a one-gesture undo. Rest-pose design (Consumed Endurance, 2014): the hand rests on the desk; pointing uses small movements + head/gaze; the arm is never required to stay raised.
5. **OS action layer (native, Windows).** The state machine's confirmed actions become real Windows input: cursor move, click, drag, scroll, app launch/switch (including Alt+Tab), typing (including shortcuts), and settings toggles — via the operating system's input injection, with a software kill switch (key + both-palms pose) and a visible enabled/disabled indicator at all times. Safety: actions are clamped (no cursor teleport), drags release if tracking is lost, and the system starts DISABLED.
6. **AR HUD overlay (the Stark layer, engineered).** A top-most, transparent, non-activating overlay (Notch's constraints: no focus theft, tiny CPU/RAM, glanceable state) showing: current mode, tracked hand/face status, focused window, pending action + confidence, and a cancel affordance; plus a magnified target for gaze pointing. The HUD is evaluated, not just drawn: the same task set runs with the HUD on and off, measuring success, time, errors and false activations — so the report can say whether the overlay helps, by how much, and where it hurts (focus theft, click-through, occlusion).

### Evaluation plan (how claims will be proven)

- **Task set:** 15–25 Windows tasks borrowed from the OSWorld / Windows Agent Arena taxonomy (file, browser, office, settings, multi-app), run by human users through the camera system AND through mouse/keyboard (the baseline that matters).
- **Metrics (reported together, never a single %):** task success, completion time, errors, false activations per session, CPU use + frame drops, lighting/occlusion/distance robustness matrix, and fatigue (Borg rating + error rise over session length).
- **Comparisons:** mouse/keyboard baseline; eViacam/Camera Mouse baseline (accessibility); HUD-on vs HUD-off; dwell vs pinch vs voice confirmation (the Midas experiment).
- **Splits:** held-out users (never train on the test user's face/hands); varied lighting; a second person briefly in frame (attention-ownership test).
- **Honesty rules:** accuracy is reported only where measured; agent benchmark scores are never presented as human baselines; dataset licences are checked before redistribution; paywalled papers are cited from their abstracts/secondary sources and marked as such where full text was not read.

### Plan (phases)

- **Phase 1 — Research (this report, complete 27 Oct 2026).** Literature, datasets, gaps, methodology, plan, references, vision. No software yet, by design.
- **Phase 2 — Prototype (next).** Single-channel prototype (hand tracking → cursor/click) on Windows; then the full state machine + HUD; then gaze + voice channels. Each step demoed against 3–5 tasks before widening.
- **Phase 3 — Evaluation.** Full task set, baselines, robustness matrix, fatigue study, HUD-on/off comparison, false-activation experiment.
- **Phase 4 — Demo + final submission.** Live demo on the student's Windows laptop (webcam only), final report with measured results, public trace dataset + reporting template, code and report in the Major-Project repository.

### Vision (Stark-like, in real human terms)

Morning. You sit down at your laptop. The webcam wakes — nothing to wear, nothing to plug in. You raise a hand, and the screen answers: a calm overlay shows it sees you, shows the window you are looking at, and waits for you to mean something. You point at Spotify; a pinch opens it. You glance at the volume; a small hand movement turns it down. You circle an error message and ask what it means. You never touch the mouse — not because the mouse is gone, but because, for this task, you did not need it. When you are done, one gesture locks the camera off, and the laptop is just a laptop again. That is the whole ambition: the computer paying attention the way a good assistant does — visibly, confirmably, and only when you want it.

---

## References

1. Zhang, F., Bazarevsky, V., Vakunov, A., Tkachenka, A., Sung, G., Chang, C.-L. & Grundmann, M. (2020). *MediaPipe Hands: On-device Real-time Hand Tracking.* arXiv:2006.10214. https://ar5iv.labs.arxiv.org/html/2006.10214
2. Molchanov, P., Yang, X., Kim, S., Hu, X., Li, K. & Kautz, J. (2016). *Online Detection and Classification of Dynamic Hand Gestures with Recurrent 3D Convolutional Neural Networks.* Proc. CVPR 2016. https://research.nvidia.com/publication/2016-06_online-detection-and-classification-dynamic-hand-gestures-recurrent-3d
3. Betke, M., Gips, J. & Fleming, P. (2002). *The Camera Mouse: Visual Tracking of Body Features to Provide Computer Access for People with Severe Disabilities.* IEEE Trans. Neural Syst. Rehabil. Eng. 10(1), 1–10. https://www.cs.clarku.edu/~jmagee/cs201/hw/Betke-Gips-Fleming-NSRE02.pdf
4. Jacob, R. J. K. (1991). *The Use of Eye Movements in Human-Computer Interaction Techniques: What You Look At Is What You Get.* ACM Trans. Inf. Syst. 9(3), 152–169. https://marcjohnson.fr/wp-content/uploads/2020/12/1991-Jacob-The-Use-of-Eye-Movements-in-human-computer-interaction-techniques.pdf
5. Papoutsaki, A., Sangkloy, P., Laskey, J., Daskalova, N., Huang, J. & Hays, J. (2016). *WebGazer: Scalable Webcam Eye Tracking Using User Interactions.* Proc. IJCAI 2016, pp. 3839–3845. https://webgazer.cs.brown.edu/
6. Krafka, K., Khosla, A., Kellnhofer, P., Kannan, H., Bhandarkar, S., Matusik, W. & Torralba, A. (2016). *Eye Tracking for Everyone.* Proc. CVPR 2016, pp. 2176–2184. https://cdfg.mit.edu/publications/eye-tracking-everyone
7. Zhang, X., Sugano, Y., Fritz, M. & Bulling, A. (2015). *Appearance-Based Gaze Estimation in the Wild.* Proc. CVPR 2015. https://arxiv.org/pdf/1504.02863
8. Zhang, X., Park, S., Beeler, T., Bradley, D., Tang, S. & Hilliges, O. (2020). *ETH-XGaze: A Large Scale Dataset for Gaze Estimation Under Extreme Head Pose and Gaze Variation.* Proc. ECCV 2020, pp. 365–381. https://ait.ethz.ch/xgaze
9. Xie, T. et al. (2024). *OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments.* NeurIPS 2024. https://arxiv.org/pdf/2404.07972.pdf
10. Bonatti, R. et al. (2025). *Windows Agent Arena: Evaluating Multi-Modal OS Agents at Scale.* Proc. ICML 2025, PMLR 267. https://proceedings.mlr.press/v267/bonatti25a.html
11. Hincapié-Ramos, J. D., Guo, X., Moghadasian, P. & Irani, P. (2014). *Consumed Endurance: A Metric to Quantify Arm Fatigue of Mid-Air Interactions.* Proc. CHI 2014, pp. 1063–1072. http://hci.cs.umanitoba.ca/assets/publication_files/Consumed_Endurance_-_CHI_2014.pdf
12. Marguet, E., Borowski, M., Kristensen, J. B., Klokmose, C. N. & Elmqvist, N. (2025). *WindowSpace: A Web-Based XR Window Manager for Interacting with 2D Windows in Immersive 3D Space.* Proc. ACM Hum.-Comput. Interact. 9(8), 119–144. https://dl.acm.org/doi/10.1145/3773063
13. Bolt, R. A. (1980). *Put-That-There: Voice and Gesture at the Graphics Interface.* Proc. SIGGRAPH 1980, pp. 262–270. (Cited via secondary sources; verify page numbers in ACM DL before submitting.)
14. Casiez, G., Roussel, N. & Vogel, D. (2012). *1€ Filter: A Simple Speed-Based Low-Pass Filter for Noisy Input in Interactive Systems.* Proc. CHI 2012, pp. 2527–2530. https://doi.org/10.1145/2207676.2208639
15. Kapitanov, A. et al. (2024). *HaGRID — HAnd Gesture Recognition Image Dataset.* Proc. WACV 2024. https://arxiv.org/html/2206.08219v2
16. Kellnhofer, P., Recasens, A., Stent, S., Matusik, W. & Torralba, A. (2019). *Gaze360: Physically Unconstrained Gaze Estimation in the Wild.* Proc. ICCV 2019, pp. 6912–6921. (Dataset site named in paper: gaze360.csail.mit.edu.)
17. Yin, Y. et al. (2016). *CamK: A Camera-based Keyboard for Small Mobile Devices.* Proc. IEEE INFOCOM 2016. https://www.bebek1113.com/_upload/tpl/02/e0/736/template736/YinPaper/INFOCOM2016Yin.pdf
18. TheCidSama/GhostyNav (GitHub repository, MIT). *GhostyNav — Dynamic Island-style notch overlay for Windows with a pixel-ghost voice assistant.* https://github.com/TheCidSama/GhostyNav — Cited as a related system only (verified by direct repository read 27 Oct 2026; not peer-reviewed evidence). See transparency note in Related systems.

---

## Appendix — What could not be verified (honesty notes)

- **Live Google Scholar citation counts** were not retrieved; no counts are claimed. Any count added later must be re-checked on Scholar on the day of writing and dated.
- **Dataset licences** (HaGRID, Jester, GazeCapture, ETH-XGaze, Gaze360) were not stated in the sources checked; check each dataset page/repo before use or redistribution.
- **Paywalled papers** (notably WindowSpace and some ACM/IEEE texts) were verified from abstracts, indexes and secondary sources, not live full-text reads; where a detail rests on secondary sourcing it is flagged in the text.
- **WebGazer accuracy units** disagree across sources (4.17° vs 130–257 px); the original IJCAI paper should be re-read before quoting one figure in a dissertation.
- **OSWorld / Windows Agent Arena scores are agent scores**, not human-camera scores, and must never be presented as a baseline a gesture system has "beaten" without running the same tasks with human input.
- **GhostyNav verification:** an independent web search in this review could not confirm GhostyNav, while a direct read of its public GitHub repository (TheCidSama/GhostyNav, README and description, 27 Oct 2026) confirms it exists as described. It is therefore cited as a related system on the basis of that repository read, not as peer-reviewed evidence, and no claim is made beyond what its README states.
- **MPIIGaze / ETH-XGaze / WindowSpace headline accuracy:** no single % was found in the sources checked; this report says "Not reported" rather than borrowing a number from a later benchmark with a different protocol.
