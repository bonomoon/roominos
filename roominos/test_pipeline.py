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

    def ask(self, prompt, system=""):
        self.call_count += 1
        if "Analyze" in prompt or "analyze" in prompt:
            return LLMResponse(content="Found 3 functions: main, calc_interest, proc_settlement. 5 EXEC SQL statements.", tokens_used=100, model="mock")
        elif "plan" in prompt.lower() or "Plan" in prompt:
            return LLMResponse(content='[{"path": "src/main/java/com/example/Entity.java", "description": "JPA entity", "type": "entity"}]', tokens_used=100, model="mock")
        elif "Create" in prompt or "create" in prompt:
            return LLMResponse(content="package com.example;\n\npublic class Entity {\n    private Long id;\n}", tokens_used=200, model="mock")
        return LLMResponse(content="OK", tokens_used=50, model="mock")


def test_pipeline_runs_all_stages():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLM()
        pipeline = Pipeline(llm=llm, output_dir=tmpdir)
        results = pipeline.run("int main() { return 0; }", source_path="test.pc")

        assert len(results) == 4
        assert results[0].stage == "analyze"
        assert results[1].stage == "plan"
        assert results[2].stage == "implement"
        assert results[3].stage == "verify"
        assert all(r.success for r in results)


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
