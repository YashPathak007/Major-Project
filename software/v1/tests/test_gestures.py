"""Gesture dictionary tests — PLAN.md §1.2 (G0–G5, one meaning each)."""

from touchless.gestures import (
    EV_CLICK, EV_DRAG_END, EV_DRAG_START, EV_GATE, EV_HOLD_CLICK,
    EV_HOLD_PROGRESS, EV_PAUSE_GESTURE, EV_SCROLL, POSE_FIST,
    POSE_NONE, POSE_OPEN_PALM, POSE_PINCH, GestureEngine, classify_pose,
)
from conftest import (
    FakeClock, feed_pose, fist_landmarks, idle_landmarks,
    open_palm_landmarks, pinch_landmarks,
)


def kinds(events):
    return [e.kind for e in events]


def test_classify_poses():
    assert classify_pose(open_palm_landmarks())[0] == POSE_OPEN_PALM
    assert classify_pose(fist_landmarks())[0] == POSE_FIST
    assert classify_pose(pinch_landmarks())[0] == POSE_PINCH
    assert classify_pose(idle_landmarks())[0] == POSE_NONE


def test_gate_requires_hold_not_flash():
    clock = FakeClock()
    engine = GestureEngine(clock=clock)
    events = feed_pose(engine, open_palm_landmarks(), (960, 540), clock, frames=2)
    assert EV_GATE not in kinds(events)  # held only briefly so far
    clock.advance(0.4)
    events = feed_pose(engine, open_palm_landmarks(), (960, 540), clock, frames=2)
    assert EV_GATE in kinds(events)
    # Gate fires once per hold, not repeatedly.
    events = feed_pose(engine, open_palm_landmarks(), (960, 540), clock, frames=3)
    assert EV_GATE not in kinds(events)


def test_quick_pinch_clicks_on_release_only():
    clock = FakeClock()
    engine = GestureEngine(hold_time_ms=600, clock=clock)
    feed_pose(engine, pinch_landmarks(), (960, 540), clock, frames=3)
    assert EV_CLICK not in kinds(feed_pose(engine, pinch_landmarks(), (960, 540), clock, frames=1))
    events = feed_pose(engine, idle_landmarks(), (960, 540), clock, frames=2)
    assert EV_CLICK in kinds(events)
    assert EV_HOLD_CLICK not in kinds(events)
    assert EV_DRAG_START not in kinds(events)


def test_hold_pinch_fires_ring_click_not_drag_or_quick_click():
    clock = FakeClock()
    engine = GestureEngine(hold_time_ms=600, clock=clock)
    feed_pose(engine, pinch_landmarks(), (960, 540), clock, frames=3)
    clock.advance(0.3)
    events = feed_pose(engine, pinch_landmarks(), (960, 540), clock, frames=2)
    assert EV_HOLD_PROGRESS in kinds(events)
    assert EV_HOLD_CLICK not in kinds(events)
    clock.advance(0.4)  # past the 600 ms ring
    events = feed_pose(engine, pinch_landmarks(), (960, 540), clock, frames=2)
    assert EV_HOLD_CLICK in kinds(events)
    # Release after a completed ring: no second click, no drag.
    events = feed_pose(engine, idle_landmarks(), (960, 540), clock, frames=2)
    assert EV_CLICK not in kinds(events)
    assert EV_DRAG_START not in kinds(events)
    assert EV_DRAG_END not in kinds(events)


def test_pinch_move_before_ring_becomes_drag():
    clock = FakeClock()
    engine = GestureEngine(hold_time_ms=600, drag_threshold_px=12, clock=clock)
    feed_pose(engine, pinch_landmarks(), (960, 540), clock, frames=3)
    clock.advance(0.2)
    events = feed_pose(engine, pinch_landmarks(), (1000, 540), clock, frames=2)
    assert EV_DRAG_START in kinds(events)
    assert EV_HOLD_CLICK not in kinds(events)
    events = feed_pose(engine, idle_landmarks(), (1000, 540), clock, frames=2)
    assert EV_DRAG_END in kinds(events)
    assert EV_CLICK not in kinds(events)


def test_small_tremble_does_not_become_drag():
    clock = FakeClock()
    engine = GestureEngine(hold_time_ms=600, drag_threshold_px=12, clock=clock)
    feed_pose(engine, pinch_landmarks(), (960, 540), clock, frames=3)
    events = feed_pose(engine, pinch_landmarks(), (965, 542), clock, frames=2)
    assert EV_DRAG_START not in kinds(events)


def test_open_palm_vertical_move_scrolls_with_sign():
    clock = FakeClock()
    engine = GestureEngine(clock=clock)
    feed_pose(engine, open_palm_landmarks(), (960, 540), clock, frames=3)
    clock.advance(0.1)
    events = feed_pose(engine, open_palm_landmarks(), (960, 470), clock, frames=2)
    scrolls = [e for e in events if e.kind == EV_SCROLL]
    assert scrolls and scrolls[0].data["lines"] > 0  # hand up -> scroll up
    clock.advance(0.1)
    events = feed_pose(engine, open_palm_landmarks(), (960, 560), clock, frames=2)
    scrolls = [e for e in events if e.kind == EV_SCROLL]
    assert scrolls and scrolls[0].data["lines"] < 0  # hand down -> scroll down


def test_open_palm_held_still_does_not_scroll():
    clock = FakeClock()
    engine = GestureEngine(clock=clock)
    events = feed_pose(engine, open_palm_landmarks(), (960, 540), clock, frames=6)
    assert EV_SCROLL not in kinds(events)


def test_fist_hold_pauses_but_brief_fist_does_not():
    clock = FakeClock()
    engine = GestureEngine(clock=clock)
    feed_pose(engine, fist_landmarks(), (960, 540), clock, frames=3)
    clock.advance(0.3)
    events = feed_pose(engine, fist_landmarks(), (960, 540), clock, frames=2)
    assert EV_PAUSE_GESTURE not in kinds(events)
    clock.advance(0.5)
    events = feed_pose(engine, fist_landmarks(), (960, 540), clock, frames=2)
    assert EV_PAUSE_GESTURE in kinds(events)


def test_single_frame_flicker_is_ignored():
    from touchless.gestures import HandFrame
    clock = FakeClock()
    engine = GestureEngine(clock=clock)
    feed_pose(engine, idle_landmarks(), (960, 540), clock, frames=3)
    # One pinch frame must not start a pinch session (needs 2 frames).
    events = engine.process(HandFrame(pinch_landmarks(), "Right", clock.now), (960, 540))
    assert EV_CLICK not in kinds(events)
    events = engine.process(HandFrame(idle_landmarks(), "Right", clock.now), (960, 540))
    assert EV_CLICK not in kinds(events)


def test_disabled_scroll_gesture_emits_nothing():
    clock = FakeClock()
    engine = GestureEngine(clock=clock,
                           gestures_enabled={"scroll": False, "click": True,
                                             "hold_click": True, "drag": True,
                                             "gesture_pause": True})
    feed_pose(engine, open_palm_landmarks(), (960, 540), clock, frames=3)
    clock.advance(0.1)
    events = feed_pose(engine, open_palm_landmarks(), (960, 470), clock, frames=2)
    assert EV_SCROLL not in kinds(events)
