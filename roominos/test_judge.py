"""Tests for AI-as-a-Judge"""
import pytest
from unittest.mock import MagicMock
from roominos.judge import Judge, Verdict, JudgeResult
from roominos.llm import LLMResponse


class MockJudgeLLM:
    def ask(self, prompt, system=""):
        return LLMResponse(
            content=(
                "CRITERION 1: PASS (95%) - Entity uses @SequenceGenerator\n"
                "CRITERION 2: PASS (90%) - BigDecimal used for balance\n"
                "CRITERION 3: FAIL (85%) - No test file | FIX: Create UserServiceTest.java"
            ),
            tokens_used=200,
            model="mock"
        )


def test_judge_evaluates_criteria():
    judge = Judge(llm=MockJudgeLLM())
    files = {"Entity.java": "public class Entity { @SequenceGenerator ... }"}
    criteria = [
        "Entity uses @SequenceGenerator",
        "BigDecimal for money",
        "Test file exists"
    ]
    result = judge.evaluate(files, criteria)

    assert len(result.verdicts) == 3
    assert result.pass_count == 2
    assert result.fail_count == 1
    assert result.score == pytest.approx(66.67, rel=0.1)
    assert not result.overall_pass


def test_judge_parse_pass():
    judge = Judge(llm=MockJudgeLLM())
    result = judge.evaluate({"f.java": "code"}, ["criterion1", "criterion2", "criterion3"])
    assert result.verdicts[0].passed is True
    assert result.verdicts[0].confidence == 95


def test_judge_parse_fail_with_fix():
    judge = Judge(llm=MockJudgeLLM())
    result = judge.evaluate({"f.java": "code"}, ["c1", "c2", "c3"])
    fail = result.verdicts[2]
    assert fail.passed is False
    assert "UserServiceTest" in fail.fix_instruction


def test_judge_format_report():
    judge = Judge(llm=MockJudgeLLM())
    result = judge.evaluate({"f.java": "code"}, ["c1", "c2", "c3"])
    report = judge.format_report(result)
    assert "FAIL" in report
    assert "FIX:" in report
    assert "66%" in report or "67%" in report


def test_judge_all_pass():
    class AllPassLLM:
        def ask(self, prompt, system=""):
            return LLMResponse(
                content="CRITERION 1: PASS (99%) - Perfect\nCRITERION 2: PASS (98%) - Good",
                tokens_used=100, model="mock"
            )

    judge = Judge(llm=AllPassLLM())
    result = judge.evaluate({"f.java": "code"}, ["c1", "c2"])
    assert result.overall_pass is True
    assert result.score == 100.0
