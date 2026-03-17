"""Session memory — learn from past runs to improve future performance."""
import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class RunRecord:
    timestamp: str
    source: str
    model: str
    tokens_used: int
    time_seconds: float
    score: float  # Judge score 0-100
    files_created: int
    retries: int
    failures: list[str] = field(default_factory=list)  # What went wrong
    learnings: list[str] = field(default_factory=list)  # What to do differently


class Memory:
    def __init__(self, path: str = ".roominos/memory.json"):
        self.path = path
        self.records: list[RunRecord] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                data = json.load(f)
                self.records = [RunRecord(**r) for r in data.get("records", [])]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump({"records": [asdict(r) for r in self.records]}, f, indent=2)

    def add(self, record: RunRecord):
        self.records.append(record)
        self.save()

    def get_learnings(self) -> str:
        """Extract learnings from past runs to inject into prompts."""
        if not self.records:
            return ""

        # Get unique failures and learnings from recent runs
        recent = self.records[-10:]  # Last 10 runs
        failures = set()
        learnings = set()

        for r in recent:
            failures.update(r.failures)
            learnings.update(r.learnings)

        if not failures and not learnings:
            return ""

        parts = ["[MEMORY] Learnings from past runs:"]
        if failures:
            parts.append("Common mistakes to avoid:")
            for f in list(failures)[:5]:
                parts.append(f"  - {f}")
        if learnings:
            parts.append("What works well:")
            for l in list(learnings)[:5]:
                parts.append(f"  + {l}")

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """Get performance statistics."""
        if not self.records:
            return {}
        return {
            "total_runs": len(self.records),
            "avg_score": sum(r.score for r in self.records) / len(self.records),
            "avg_tokens": sum(r.tokens_used for r in self.records) // len(self.records),
            "avg_time": sum(r.time_seconds for r in self.records) / len(self.records),
            "best_score": max(r.score for r in self.records),
            "total_tokens": sum(r.tokens_used for r in self.records),
        }
