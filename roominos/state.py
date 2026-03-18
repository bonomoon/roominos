"""State machine for pipeline execution with backtracking."""
import json
import os
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime


class State(Enum):
    INIT = "init"
    ANALYZE = "analyze"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REFLECT = "reflect"
    VERIFY = "verify"
    BACKTRACK = "backtrack"
    COMPLETE = "complete"
    FAILED = "failed"


TRANSITIONS = {
    State.INIT: {True: State.ANALYZE, False: State.FAILED},
    State.ANALYZE: {True: State.PLAN, False: State.FAILED},
    State.PLAN: {True: State.IMPLEMENT, False: State.ANALYZE},  # backtrack
    State.IMPLEMENT: {True: State.REFLECT, False: State.PLAN},  # backtrack
    State.REFLECT: {True: State.VERIFY, False: State.VERIFY},   # always verify
    State.VERIFY: {True: State.COMPLETE, False: State.BACKTRACK},
    State.BACKTRACK: {True: State.IMPLEMENT, False: State.FAILED},  # retry
}


@dataclass
class Checkpoint:
    state: str
    timestamp: str
    artifacts: dict = field(default_factory=dict)
    tokens_used: int = 0
    attempt: int = 0


class StateMachine:
    """Deterministic state machine for pipeline with backtracking."""

    def __init__(self, checkpoint_dir: str = ".roominos/checkpoints", max_backtrack: int = 3):
        self.checkpoint_dir = checkpoint_dir
        self.max_backtrack = max_backtrack
        self.current_state = State.INIT
        self.checkpoints: list[Checkpoint] = []
        self.backtrack_count = 0

    def transition(self, success: bool) -> State:
        """Move to next state based on success/failure."""
        if self.current_state == State.BACKTRACK:
            self.backtrack_count += 1
            if self.backtrack_count >= self.max_backtrack:
                self.current_state = State.FAILED
                return self.current_state

        transitions = TRANSITIONS.get(self.current_state, {})
        next_state = transitions.get(success, State.FAILED)
        self.current_state = next_state
        return next_state

    def save_checkpoint(self, artifacts: dict = None, tokens: int = 0):
        """Save current state as a checkpoint."""
        cp = Checkpoint(
            state=self.current_state.value,
            timestamp=datetime.now().isoformat(),
            artifacts=artifacts or {},
            tokens_used=tokens,
            attempt=self.backtrack_count
        )
        self.checkpoints.append(cp)

        os.makedirs(self.checkpoint_dir, exist_ok=True)
        path = os.path.join(self.checkpoint_dir, f"checkpoint_{len(self.checkpoints):03d}.json")
        with open(path, 'w') as f:
            json.dump(asdict(cp), f, indent=2)

    def restore_checkpoint(self, index: int = -1) -> Checkpoint | None:
        """Restore a previous checkpoint."""
        if not self.checkpoints:
            return None
        cp = self.checkpoints[index]
        self.current_state = State(cp.state)
        return cp

    def can_backtrack(self) -> bool:
        return self.backtrack_count < self.max_backtrack

    @property
    def is_terminal(self) -> bool:
        return self.current_state in (State.COMPLETE, State.FAILED)
