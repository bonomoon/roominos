"""Refactor skill — modernize legacy Java code."""
from .base import BaseSkill


class RefactorSkill(BaseSkill):
    name = "refactor"
    description = "Modernize legacy Java code (Spring Boot upgrade, pattern improvements)"

    def analyze_system(self) -> str:
        return "You are a code modernization expert. Identify: deprecated APIs, anti-patterns, missing annotations, outdated dependencies."

    def plan_system(self) -> str:
        return "Plan refactoring changes. 1-2 files per batch. Prioritize: breaking changes first, then improvements."

    def implement_system(self) -> str:
        return "Refactor the code. Preserve all existing functionality. Use modern Java patterns."

    def verify_criteria(self) -> list[str]:
        return [
            "No deprecated API usage",
            "Modern Spring Boot patterns",
            "Constructor injection",
            "Proper exception handling",
            "Tests updated for changes",
        ]
