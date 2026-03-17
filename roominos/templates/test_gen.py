"""Test generation skill — create tests for existing code."""
from .base import BaseSkill


class TestGenSkill(BaseSkill):
    name = "test-gen"
    description = "Generate JUnit tests for existing Java code"

    def analyze_system(self) -> str:
        return "You are a QA engineer. Identify: testable methods, edge cases, dependencies to mock, integration points."

    def plan_system(self) -> str:
        return "Plan test files. 1 test class per source class. Include: unit tests, integration tests."

    def implement_system(self) -> str:
        return (
            "Create JUnit 5 tests. Use: @SpringBootTest, @MockBean, AssertJ assertions.\n"
            "Test naming: should_[expected]_when_[condition].\n"
            "Cover: happy path, error cases, edge cases, null handling."
        )

    def verify_criteria(self) -> list[str]:
        return [
            "Test class for each service",
            "@SpringBootTest annotation",
            "At least 3 test methods per class",
            "Error case coverage",
            "Null/edge case coverage",
        ]
