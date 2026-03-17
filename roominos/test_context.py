"""Tests for ContextBudget"""
import pytest
from roominos.context import ContextBudget

def test_estimate_tokens():
    budget = ContextBudget()
    assert budget.estimate_tokens("hello world!") == 3  # 12 chars / 4

def test_chunk_small_text():
    budget = ContextBudget()
    chunks = budget.chunk_text("line1\nline2\nline3", max_lines=200)
    assert len(chunks) == 1

def test_chunk_large_text():
    budget = ContextBudget()
    text = "\n".join(f"line {i}" for i in range(500))
    chunks = budget.chunk_text(text, max_lines=200)
    assert len(chunks) == 3

def test_summarize_short():
    budget = ContextBudget()
    text = "short text"
    assert budget.summarize(text) == text

def test_summarize_long():
    budget = ContextBudget()
    text = "x" * 5000
    result = budget.summarize(text, max_chars=100)
    assert len(result) < 5000
    assert "truncated" in result

def test_remaining():
    budget = ContextBudget(max_tokens=1000)
    assert budget.remaining() == 1000
    budget.use(300)
    assert budget.remaining() == 700

def test_fits():
    budget = ContextBudget(max_tokens=100)
    assert budget.fits("x" * 400) is True   # 100 tokens
    assert budget.fits("x" * 404) is False   # 101 tokens > 100

def test_trim_to_budget():
    budget = ContextBudget(max_tokens=100)
    budget.use(50)  # 50 remaining
    text = "x" * 500  # 125 tokens, too big
    trimmed = budget.trim_to_budget(text)
    assert len(trimmed) < 500
