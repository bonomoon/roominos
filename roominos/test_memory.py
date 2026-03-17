"""Tests for Memory system"""
import os
import tempfile
import pytest
from roominos.memory import Memory, RunRecord


def test_memory_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, ".roominos", "memory.json")
        mem = Memory(path=path)
        mem.add(RunRecord(
            timestamp="2026-03-17T10:00:00",
            source="test.pc",
            model="gpt-oss-20b",
            tokens_used=1000,
            time_seconds=30.0,
            score=80.0,
            files_created=5,
            retries=1,
            failures=["Missing @Entity annotation"],
            learnings=["Use jakarta.persistence"]
        ))

        # Reload
        mem2 = Memory(path=path)
        assert len(mem2.records) == 1
        assert mem2.records[0].score == 80.0


def test_memory_learnings():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, ".roominos", "memory.json")
        mem = Memory(path=path)
        mem.add(RunRecord(
            timestamp="2026-03-17", source="a.pc", model="m",
            tokens_used=100, time_seconds=10, score=60,
            files_created=3, retries=1,
            failures=["Used Double instead of BigDecimal"],
            learnings=["Always use BigDecimal for money"]
        ))

        learnings = mem.get_learnings()
        assert "BigDecimal" in learnings
        assert "MEMORY" in learnings


def test_memory_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, ".roominos", "memory.json")
        mem = Memory(path=path)
        for i in range(3):
            mem.add(RunRecord(
                timestamp=f"2026-03-17T{i}", source="x.pc", model="m",
                tokens_used=1000*(i+1), time_seconds=30,
                score=70+i*10, files_created=5, retries=0
            ))

        stats = mem.get_stats()
        assert stats["total_runs"] == 3
        assert stats["best_score"] == 90


def test_memory_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        mem = Memory(path=os.path.join(tmpdir, "x.json"))
        assert mem.get_learnings() == ""
        assert mem.get_stats() == {}
