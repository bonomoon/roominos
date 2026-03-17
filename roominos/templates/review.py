"""Code review skill — analyze code quality."""
from .base import BaseSkill


class ReviewSkill(BaseSkill):
    name = "review"
    description = "Review code for bugs, security, and quality issues"

    def analyze_system(self) -> str:
        return "You are a security-focused code reviewer. Check: OWASP Top 10, SQL injection, XSS, hardcoded secrets."

    def plan_system(self) -> str:
        return "Organize review findings by severity: CRITICAL, WARNING, INFO."

    def implement_system(self) -> str:
        return "Generate a review report with specific file:line references and fix suggestions."

    def verify_criteria(self) -> list[str]:
        return [
            "All CRITICAL findings addressed",
            "No SQL injection vulnerabilities",
            "No hardcoded credentials",
            "Input validation present",
            "Proper error handling",
        ]
