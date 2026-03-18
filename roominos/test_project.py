"""Tests for multi-file project pipeline."""
import os
import tempfile
import pytest
from roominos.project import ProjectPipeline, FileInfo
from roominos.pipeline import Pipeline


class MockProjectLLM:
    model = "mock"

    def ask(self, prompt, system="", max_retries=3):
        from roominos.llm import LLMResponse
        if "architect" in system.lower() or "project" in prompt.lower():
            return LLMResponse(content="This is a batch processing system with 3 modules.", tokens_used=100, model="mock")
        if "plan" in prompt.lower():
            return LLMResponse(content='[{"path": "src/main/java/Entity.java", "description": "entity", "type": "entity"}]', tokens_used=100, model="mock")
        if "review" in prompt.lower() or "Review" in prompt:
            return LLMResponse(content="NO_ISSUES", tokens_used=50, model="mock")
        if "criterion" in prompt.lower() or "evaluate" in prompt.lower():
            return LLMResponse(content="CRITERION 1: PASS (95%) - OK", tokens_used=50, model="mock")
        return LLMResponse(content="package com.example;\npublic class Entity {}", tokens_used=100, model="mock")


def test_index_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test source files
        os.makedirs(os.path.join(tmpdir, "src"))
        with open(os.path.join(tmpdir, "src/main.pc"), 'w') as f:
            f.write('#include "common.h"\nEXEC SQL SELECT * FROM USERS;\nint main() { return 0; }\n')
        with open(os.path.join(tmpdir, "src/common.h"), 'w') as f:
            f.write('#define MAX 100\ntypedef struct { int id; } USER;\n')

        llm = MockProjectLLM()
        pp = ProjectPipeline(llm=llm, output_dir=os.path.join(tmpdir, "out"))
        files = pp._index_project(os.path.join(tmpdir, "src"))

        assert len(files) == 2
        paths = {f.path for f in files}
        assert "main.pc" in paths or "src/main.pc" in paths


def test_dependency_order():
    files = [
        FileInfo(path="main.pc", lines=100, index="...", dependencies=["common.h"]),
        FileInfo(path="common.h", lines=50, index="..."),
        FileInfo(path="util.c", lines=200, index="...", dependencies=["common.h"]),
    ]
    pp = ProjectPipeline(llm=None, output_dir="/tmp/test")
    ordered = pp._dependency_order(files)
    # Headers first
    assert ordered[0].path == "common.h"


def test_format_report():
    pp = ProjectPipeline(llm=None, output_dir="/tmp/test")
    pp.results = [
        {"file": "main.pc", "lines": 100, "score": 100.0, "files_created": 5, "results": []},
        {"file": "util.c", "lines": 50, "score": 75.0, "files_created": 3, "results": []},
    ]
    pp.total_tokens = 10000
    report = pp.format_report()
    assert "100%" in report
    assert "75%" in report
