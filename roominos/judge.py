"""AI-as-a-Judge — validates generated code against acceptance criteria."""
import re
from dataclasses import dataclass, field
from .llm import LLMClient, LLMResponse


@dataclass
class Verdict:
    criterion: str
    passed: bool
    confidence: int  # 0-100
    reason: str
    fix_instruction: str = ""


@dataclass
class JudgeResult:
    verdicts: list[Verdict]
    overall_pass: bool
    tokens_used: int

    @property
    def pass_count(self) -> int:
        return sum(1 for v in self.verdicts if v.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for v in self.verdicts if not v.passed)

    @property
    def score(self) -> float:
        if not self.verdicts:
            return 0.0
        return self.pass_count / len(self.verdicts) * 100


class Judge:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def evaluate(self, files: dict[str, str], criteria: list[str]) -> JudgeResult:
        """
        Evaluate generated files against acceptance criteria.
        files: dict of {path: content}
        criteria: list of acceptance criteria strings
        """
        # Build file summary (truncated to save tokens)
        file_summary = ""
        for path, content in files.items():
            lines = content.split('\n')
            if len(lines) > 50:
                preview = '\n'.join(lines[:30]) + f"\n... [{len(lines)-30} more lines]"
            else:
                preview = content
            file_summary += f"\n### {path}\n```\n{preview}\n```\n"

        criteria_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))

        prompt = f"""You are a code review judge. Evaluate the following files against the acceptance criteria.

## Files Generated
{file_summary}

## Acceptance Criteria
{criteria_text}

## Instructions
For EACH criterion, output exactly one line in this format:
CRITERION N: PASS (confidence%) - reason
or
CRITERION N: FAIL (confidence%) - reason | FIX: specific fix instruction

Example:
CRITERION 1: PASS (95%) - Entity uses @SequenceGenerator correctly
CRITERION 2: FAIL (90%) - No test file found | FIX: Create SettlementServiceTest.java with @SpringBootTest

Evaluate ALL criteria. Output ONLY the verdict lines, nothing else."""

        resp = self.llm.ask(prompt, system="You are a strict code reviewer. Be precise and honest.")
        verdicts = self._parse_verdicts(resp.content, criteria)

        return JudgeResult(
            verdicts=verdicts,
            overall_pass=all(v.passed for v in verdicts),
            tokens_used=resp.tokens_used
        )

    def _parse_verdicts(self, response: str, criteria: list[str]) -> list[Verdict]:
        """Parse CRITERION N: PASS/FAIL lines from judge response."""
        verdicts = []

        for i, criterion in enumerate(criteria):
            pattern = rf'CRITERION\s*{i+1}\s*:\s*(PASS|FAIL)\s*\((\d+)%\)\s*-\s*(.*?)(?:\|\s*FIX:\s*(.*))?$'
            match = re.search(pattern, response, re.MULTILINE | re.IGNORECASE)

            if match:
                passed = match.group(1).upper() == "PASS"
                confidence = int(match.group(2))
                reason = match.group(3).strip()
                fix = match.group(4).strip() if match.group(4) else ""
                verdicts.append(Verdict(
                    criterion=criterion,
                    passed=passed,
                    confidence=confidence,
                    reason=reason,
                    fix_instruction=fix
                ))
            else:
                # Default to FAIL if can't parse
                verdicts.append(Verdict(
                    criterion=criterion,
                    passed=False,
                    confidence=0,
                    reason="Could not parse judge response for this criterion",
                    fix_instruction=""
                ))

        return verdicts

    def format_report(self, result: JudgeResult) -> str:
        """Format judge result as human-readable report."""
        lines = [
            f"## Judge Report — {result.score:.0f}% ({result.pass_count}/{len(result.verdicts)})",
            ""
        ]
        for v in result.verdicts:
            icon = "✅" if v.passed else "❌"
            lines.append(f"{icon} [{v.confidence}%] {v.criterion}")
            lines.append(f"   {v.reason}")
            if v.fix_instruction:
                lines.append(f"   FIX: {v.fix_instruction}")
            lines.append("")

        lines.append(f"Overall: {'PASS' if result.overall_pass else 'FAIL'}")
        lines.append(f"Tokens: {result.tokens_used}")
        return "\n".join(lines)
