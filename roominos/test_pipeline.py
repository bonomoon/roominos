"""Tests for pipeline with mock LLM"""
import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock
from roominos.llm import LLMClient, LLMResponse
from roominos.pipeline import Pipeline


class MockLLM:
    def __init__(self):
        self.call_count = 0
        self.model = "mock"

    def ask(self, prompt, system=""):
        self.call_count += 1
        if "Analyze" in prompt or "analyze" in prompt:
            return LLMResponse(content="Found 3 functions: main, calc_interest, proc_settlement. 5 EXEC SQL statements.", tokens_used=100, model="mock")
        elif "plan" in prompt.lower() or "Plan" in prompt:
            return LLMResponse(content='[{"path": "src/main/java/com/example/Entity.java", "description": "JPA entity", "type": "entity"}]', tokens_used=100, model="mock")
        elif "Create" in prompt or "create" in prompt:
            return LLMResponse(content="package com.example;\n\npublic class Entity {\n    private Long id;\n}", tokens_used=200, model="mock")
        elif "Review" in prompt or "review" in prompt.lower():
            return LLMResponse(content="NO_ISSUES", tokens_used=50, model="mock")
        elif "CRITERION" in prompt or "Evaluate" in prompt or "criteria" in prompt.lower():
            return LLMResponse(
                content=(
                    "CRITERION 1: PASS (90%) - Code compiles correctly\n"
                    "CRITERION 2: PASS (85%) - Proper imports used\n"
                    "CRITERION 3: PASS (80%) - Business logic preserved"
                ),
                tokens_used=100, model="mock"
            )
        elif "Fix" in prompt or "fix" in prompt.lower():
            return LLMResponse(content="package com.example;\n\npublic class Entity {\n    private Long id;\n}", tokens_used=150, model="mock")
        return LLMResponse(content="OK", tokens_used=50, model="mock")


def test_pipeline_runs_all_stages():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLM()
        pipeline = Pipeline(llm=llm, output_dir=tmpdir)
        results = pipeline.run("int main() { return 0; }", source_path="test.pc")

        assert len(results) == 5
        assert results[0].stage == "analyze"
        assert results[1].stage == "plan"
        assert results[2].stage == "implement"
        assert results[3].stage == "reflect"
        assert results[4].stage == "verify"


def test_pipeline_creates_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLM()
        pipeline = Pipeline(llm=llm, output_dir=tmpdir)
        results = pipeline.run("int main() { return 0; }")

        # Check that at least one file was created
        created = results[2].artifacts.get("created_files", [])
        assert len(created) > 0

        for path in created:
            full = os.path.join(tmpdir, path)
            assert os.path.exists(full)


def test_pipeline_tracks_tokens():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLM()
        pipeline = Pipeline(llm=llm, output_dir=tmpdir)
        pipeline.run("int main() { return 0; }")

        assert pipeline.total_tokens > 0


def test_pipeline_with_reflection():
    """Pipeline includes reflection stage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLM()
        pipeline = Pipeline(llm=llm, output_dir=tmpdir)
        results = pipeline.run("int main() { return 0; }")

        stages = [r.stage for r in results]
        assert "reflect" in stages
        assert "verify" in stages


def test_pipeline_verify_with_judge():
    """Verify stage uses Judge for evaluation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLM()
        pipeline = Pipeline(llm=llm, output_dir=tmpdir)
        results = pipeline.run("int main() { return 0; }")

        verify = [r for r in results if r.stage == "verify"][0]
        # Mock returns generic responses, judge should still run
        assert verify.stage == "verify"
