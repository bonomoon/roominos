"""Tests for state machine."""
from roominos.state import StateMachine, State, TRANSITIONS


def test_happy_path():
    sm = StateMachine()
    assert sm.current_state == State.INIT
    assert sm.transition(True) == State.ANALYZE
    assert sm.transition(True) == State.PLAN
    assert sm.transition(True) == State.IMPLEMENT
    assert sm.transition(True) == State.REFLECT
    assert sm.transition(True) == State.VERIFY
    assert sm.transition(True) == State.COMPLETE
    assert sm.is_terminal


def test_verify_failure_backtracks():
    sm = StateMachine()
    sm.current_state = State.VERIFY
    assert sm.transition(False) == State.BACKTRACK
    assert sm.transition(True) == State.IMPLEMENT  # retry


def test_max_backtrack():
    sm = StateMachine(max_backtrack=2)
    sm.current_state = State.BACKTRACK
    sm.backtrack_count = 2
    assert sm.transition(True) == State.FAILED


def test_checkpoint():
    import tempfile
    import os
    with tempfile.TemporaryDirectory() as tmpdir:
        sm = StateMachine(checkpoint_dir=os.path.join(tmpdir, "cp"))
        sm.current_state = State.IMPLEMENT
        sm.save_checkpoint(artifacts={"files": ["a.java"]}, tokens=1000)

        assert len(sm.checkpoints) == 1
        assert os.path.exists(os.path.join(tmpdir, "cp", "checkpoint_001.json"))


def test_can_backtrack():
    sm = StateMachine(max_backtrack=3)
    assert sm.can_backtrack()
    sm.backtrack_count = 3
    assert not sm.can_backtrack()
