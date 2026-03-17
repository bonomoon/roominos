"""Pipeline engine: analyze → plan → implement → reflect → verify"""
import json
import os
import re
import time
from datetime import datetime
from dataclasses import dataclass, field
from .llm import LLMClient, LLMResponse
from .tools import TextToolExecutor
from .context import ContextBudget
from .memory import Memory, RunRecord


@dataclass
class StageResult:
    stage: str
    success: bool
    output: str
    tokens_used: int
    artifacts: dict = field(default_factory=dict)


class Pipeline:
    def __init__(self, llm: LLMClient, output_dir: str, template=None):
        self.llm = llm
        self.output_dir = output_dir
        self.tools = TextToolExecutor(base_dir=output_dir)
        self.budget = ContextBudget(max_tokens=24000)
        self.template = template
        self.total_tokens = 0
        self.results: list[StageResult] = []
        self.memory = Memory(path=os.path.join(output_dir, ".roominos", "memory.json"))

    def run(self, source_content: str, source_path: str = "") -> list[StageResult]:
        """Execute full pipeline: analyze → plan → implement → reflect → verify"""
        os.makedirs(self.output_dir, exist_ok=True)
        start = time.time()

        # Stage 1: Analyze
        analysis = self._analyze(source_content, source_path)
        self.results.append(analysis)
        if not analysis.success:
            return self.results

        # Stage 2: Plan
        plan = self._plan(analysis.output)
        self.results.append(plan)
        if not plan.success:
            return self.results

        # Stage 3: Implement (per file in plan)
        impl = self._implement(plan.artifacts.get("files", []), source_content)
        self.results.append(impl)

        # Stage 3.5: Self-Reflection
        reflect = self._reflect(impl.artifacts.get("created_files", []))
        self.results.append(reflect)

        # Stage 4: Verify (with Judge + auto-retry)
        verify = self._verify(impl.artifacts.get("created_files", []), source_content)
        self.results.append(verify)

        # Save to memory
        elapsed = time.time() - start
        score = 0
        if verify.artifacts.get("verdicts"):
            passed = sum(1 for v in verify.artifacts["verdicts"] if v.get("passed"))
            score = passed / len(verify.artifacts["verdicts"]) * 100 if verify.artifacts["verdicts"] else 0

        failures = []
        for v in verify.artifacts.get("verdicts", []):
            if not v.get("passed"):
                failures.append(v.get("reason", "unknown"))

        self.memory.add(RunRecord(
            timestamp=datetime.now().isoformat(),
            source=source_path,
            model=self.llm.model,
            tokens_used=self.total_tokens,
            time_seconds=elapsed,
            score=score,
            files_created=len(impl.artifacts.get("created_files", [])),
            retries=0,
            failures=failures,
            learnings=[],
        ))

        return self.results

    def _analyze(self, source: str, source_path: str) -> StageResult:
        lines = source.split('\n')
        total_lines = len(lines)
        tokens = 0

        # For large files: send summary instead of all chunks
        # Budget: analyze should use max 20% of total token budget
        max_analyze_tokens = self.budget.max_tokens // 5  # ~4800 tokens

        if total_lines > 500:
            # Large file strategy: send first 150 + last 100 lines + function signatures
            head = '\n'.join(lines[:150])
            tail = '\n'.join(lines[-100:])
            # Extract function signatures (lines with function-like patterns)
            sigs = [l.strip() for l in lines if ('(' in l and ')' in l and '{' in l) or l.strip().startswith('EXEC SQL')]
            sig_text = '\n'.join(sigs[:50])

            system = self.template.analyze_system() if self.template else "You are a code analyst."
            learnings = self.memory.get_learnings()
            if learnings:
                system = system + "\n\n" + learnings

            prompt = (
                f"Analyze this {total_lines}-line Pro*C file. I'm showing key parts:\n\n"
                f"=== FIRST 150 LINES ===\n{head}\n\n"
                f"=== LAST 100 LINES ===\n{tail}\n\n"
                f"=== FUNCTION SIGNATURES & SQL ({len(sigs)} found) ===\n{sig_text}\n\n"
                f"List concisely: all functions, all EXEC SQL statements, all tables, error handling patterns, global variables."
            )
            resp = self.llm.ask(prompt, system=system)
            tokens = resp.tokens_used
            summary = resp.content
        else:
            # Small file: analyze fully (existing behavior)
            chunks = self.budget.chunk_text(source, max_lines=200)
            analyses = []
            for i, chunk in enumerate(chunks):
                system = self.template.analyze_system() if self.template else "You are a code analyst."
                learnings = self.memory.get_learnings()
                if learnings:
                    system = system + "\n\n" + learnings
                prompt = f"Analyze this code (part {i+1}/{len(chunks)}):\n\n{chunk}\n\nList: functions, SQL statements, global variables, error handling patterns."
                resp = self.llm.ask(prompt, system=system)
                analyses.append(resp.content)
                tokens += resp.tokens_used
            summary = self.budget.summarize("\n\n".join(analyses))

        self.total_tokens += tokens
        return StageResult(stage="analyze", success=True, output=summary, tokens_used=tokens)

    def _plan(self, analysis: str) -> StageResult:
        system = self.template.plan_system() if self.template else "You are a software architect."
        prompt = f"Based on this analysis:\n\n{analysis}\n\nCreate a migration plan. List files to create, 1-2 per batch. Output as JSON array: [{{'path': '...', 'description': '...', 'type': 'entity|repository|service|config|test'}}]"

        resp = self.llm.ask(prompt, system=system)
        self.total_tokens += resp.tokens_used

        # Parse file list from response
        files = []
        try:
            match = re.search(r'\[[\s\S]*?\]', resp.content)
            if match:
                files = json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        # Ensure mandatory files are always in the plan
        existing_paths = {f.get("path", "") for f in files}
        mandatory = [
            {"path": "src/main/resources/application.yml", "description": "Spring config for Oracle datasource, NO hardcoded dialect", "type": "config"},
            {"path": "src/test/resources/application-test.yml", "description": "Test config with H2 in-memory DB, ddl-auto=create-drop", "type": "config"},
        ]
        for m in mandatory:
            if not any(m["path"] in p for p in existing_paths):
                files.append(m)

        return StageResult(stage="plan", success=len(files) > 0, output=resp.content, tokens_used=resp.tokens_used, artifacts={"files": files})

    def _implement(self, files: list, source: str) -> StageResult:
        created = []
        tokens = 0
        source_excerpt = source[:2000]  # Keep context small

        for file_spec in files:
            path = file_spec.get("path", "")
            desc = file_spec.get("description", "")

            system = self.template.implement_system() if self.template else "You are a Java developer. Output ONLY code. No explanation."
            prompt = f"Create {path}: {desc}\n\nBased on source:\n{source_excerpt}\n\nOutput ONLY the file content, no markdown fences."

            resp = self.llm.ask(prompt, system=system)
            tokens += resp.tokens_used

            # Write file
            content = self.tools.extract_code(resp.content)
            full_path = os.path.join(self.output_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            created.append(path)

        self.total_tokens += tokens
        return StageResult(stage="implement", success=len(created) > 0, output=f"Created {len(created)} files", tokens_used=tokens, artifacts={"created_files": created})

    def _reflect(self, created_files: list) -> StageResult:
        """Self-reflection: model reviews its own output before judge."""
        issues_found = 0
        tokens = 0

        # Deterministic fixes first (no LLM call needed)
        for path in created_files:
            full = os.path.join(self.output_dir, path)
            if not os.path.exists(full):
                continue
            with open(full) as f:
                content = f.read()

            changed = False
            # Remove hardcoded Hibernate dialect lines
            if "dialect" in content.lower() and ("Oracle" in content or "hibernate.dialect" in content):
                lines = content.split("\n")
                new_lines = [l for l in lines if "hibernate.dialect" not in l.lower() and "Oracle12cDialect" not in l and "OracleDialect" not in l]
                if len(new_lines) < len(lines):
                    content = "\n".join(new_lines)
                    changed = True
                    issues_found += 1

            # Fix javax → jakarta
            if "javax.persistence" in content:
                content = content.replace("javax.persistence", "jakarta.persistence")
                changed = True
                issues_found += 1

            if changed:
                with open(full, 'w') as f:
                    f.write(content)

        # LLM-based review
        for path in created_files:
            full = os.path.join(self.output_dir, path)
            if not os.path.exists(full):
                continue
            with open(full) as f:
                content = f.read()

            if len(content) < 50:  # Skip tiny files
                continue

            prompt = (
                f"Review this file for common mistakes:\n"
                f"File: {path}\n```\n{content[:2000]}\n```\n\n"
                f"Check for:\n"
                f"- Wrong imports (javax vs jakarta)\n"
                f"- Missing annotations (@Entity, @Service, @Repository)\n"
                f"- Double instead of BigDecimal for money\n"
                f"- Missing @SequenceGenerator for Oracle\n"
                f"- Missing null handling\n\n"
                f"If issues found, output the COMPLETE fixed file.\n"
                f"If no issues, output: NO_ISSUES"
            )

            resp = self.llm.ask(prompt, system="You are a strict code reviewer. Fix issues immediately.")
            tokens += resp.tokens_used

            if "NO_ISSUES" not in resp.content:
                fixed = self.tools.extract_code(resp.content)
                if len(fixed) > 50:  # Valid fix
                    with open(full, 'w') as f:
                        f.write(fixed)
                    issues_found += 1

        self.total_tokens += tokens
        return StageResult(
            stage="reflect", success=True,
            output=f"Self-reflection: fixed {issues_found} files",
            tokens_used=tokens
        )

    def _verify(self, created_files: list, source: str, max_retries: int = 3) -> StageResult:
        """AI-as-a-Judge verification with auto-retry on failure."""
        from .judge import Judge

        judge = Judge(llm=self.llm)
        criteria = self.template.verify_criteria() if self.template else [
            "Code compiles without errors",
            "Proper imports used",
            "Business logic preserved from source"
        ]

        # Read generated files
        files = {}
        for path in created_files:
            full = os.path.join(self.output_dir, path)
            if os.path.exists(full):
                with open(full) as f:
                    files[path] = f.read()

        result = None
        for attempt in range(max_retries):
            result = judge.evaluate(files, criteria)
            self.total_tokens += result.tokens_used

            if result.overall_pass:
                return StageResult(
                    stage="verify", success=True,
                    output=f"PASS {result.score:.0f}% ({result.pass_count}/{len(result.verdicts)})",
                    tokens_used=result.tokens_used,
                    artifacts={"verdicts": [v.__dict__ for v in result.verdicts]}
                )

            # Auto-retry: feed fix instructions back to implement stage
            fixes = [v for v in result.verdicts if not v.passed and v.fix_instruction]
            if fixes and attempt < max_retries - 1:
                self._apply_fixes(fixes, files, source)
                # Re-read fixed files
                for path in created_files:
                    full = os.path.join(self.output_dir, path)
                    if os.path.exists(full):
                        with open(full) as f:
                            files[path] = f.read()

        # All retries exhausted — return last result
        return StageResult(
            stage="verify", success=False,
            output=f"FAIL {result.score:.0f}% after {max_retries} attempts",
            tokens_used=result.tokens_used,
            artifacts={"verdicts": [v.__dict__ for v in result.verdicts]}
        )

    def _apply_fixes(self, fixes, files, source):
        """Re-implement files that failed verification."""
        for fix in fixes:
            # Find which file needs fixing
            for path, content in files.items():
                system = self.template.implement_system() if self.template else "You are a Java developer."
                prompt = (
                    f"Fix this file: {path}\n"
                    f"Problem: {fix.reason}\n"
                    f"Fix instruction: {fix.fix_instruction}\n\n"
                    f"Current content:\n{content[:2000]}\n\n"
                    f"Output the COMPLETE fixed file. No explanation."
                )
                resp = self.llm.ask(prompt, system=system)
                self.total_tokens += resp.tokens_used

                new_content = self.tools.extract_code(resp.content)
                full_path = os.path.join(self.output_dir, path)
                with open(full_path, 'w') as f:
                    f.write(new_content)
                break  # One fix per file
