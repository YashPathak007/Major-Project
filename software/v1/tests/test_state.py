"""State machine tests — PLAN.md §3 transition table."""

from touchless.state import ALLOWED, State, StateMachine


def test_full_transition_table():
    machine = StateMachine(State.OFF)
    for from_state, targets in ALLOWED.items():
        for target in State:
            machine.state = from_state
            machine.error_id = None
            result = machine.transition(target)
            if target in targets:
                assert result, f"{from_state} -> {target} must be allowed"
                assert machine.state is target
            else:
                assert not result, f"{from_state} -> {target} must be rejected"
                assert machine.state is from_state


def test_error_never_goes_straight_to_tracking():
    machine = StateMachine(State.ERROR)
    assert not machine.transition(State.TRACKING)
    assert machine.transition(State.PAUSED)
    assert machine.state is State.PAUSED


def test_calibrating_only_from_paused():
    machine = StateMachine(State.TRACKING)
    assert not machine.transition(State.CALIBRATING)
    machine.state = State.PAUSED
    assert machine.transition(State.CALIBRATING)


def test_injection_states():
    assert StateMachine(State.TRACKING).is_injecting
    assert StateMachine(State.DEGRADED).is_injecting
    for state in (State.PAUSED, State.HAND_LOST, State.CALIBRATING, State.ERROR, State.OFF):
        assert not StateMachine(state).is_injecting


def test_transition_sounds_and_listeners():
    machine = StateMachine(State.OFF)
    seen = []
    machine.subscribe(seen.append)
    assert machine.transition(State.PAUSED)
    assert seen[-1].sound is None  # silence on launch is deliberate (§3)
    assert machine.transition(State.TRACKING)
    assert seen[-1].sound == "activation"
    assert machine.transition(State.HAND_LOST)
    assert seen[-1].sound == "hand_lost"
    assert machine.transition(State.TRACKING)
    assert seen[-1].sound == "reacquire"
    assert machine.transition(State.PAUSED)
    assert seen[-1].sound == "pause"
    assert machine.transition(State.ERROR, "E1", "No camera found.")
    assert seen[-1].sound == "error"
    assert seen[-1].error_id == "E1"


def test_illegal_transition_keeps_state_and_error():
    machine = StateMachine(State.PAUSED)
    machine.transition(State.ERROR, "E1", "No camera found.")
    assert machine.state is State.ERROR
    assert machine.error_id == "E1"
    assert not machine.transition(State.TRACKING)
    assert machine.state is State.ERROR
    assert machine.transition(State.PAUSED)
    assert machine.error_id is None  # leaving ERROR clears the error
