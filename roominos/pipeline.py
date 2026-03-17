"""Pipeline engine: analyze → plan → implement → verify"""
import json
import os
import re
from dataclasses import dataclass, field
from .llm import LLMClient, LLMResponse
from .tools import TextToolExecutor
from .context import ContextBudget


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

    def run(self, source_content: str, source_path: str = "") -> list[StageResult]:
        """Execute full pipeline: analyze → plan → implement → verify"""
        os.makedirs(self.output_dir, exist_ok=True)

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

        # Stage 4: Verify
        verify = self._verify(impl.artifacts.get("created_files", []))
        self.results.append(verify)

        return self.results

    def _analyze(self, source: str, source_path: str) -> StageResult:
        chunks = self.budget.chunk_text(source, max_lines=200)
        analyses = []
        tokens = 0

        for i, chunk in enumerate(chunks):
            system = self.template.analyze_system() if self.template else "You are a code analyst."
            prompt = f"Analyze this code (part {i+1}/{len(chunks)}):\n\n{chunk}\n\nList: functions, SQL statements, global variables, error handling patterns."
            resp = self.llm.ask(prompt, system=system)
            analyses.append(resp.content)
            tokens += resp.tokens_used

        combined = "\n\n".join(analyses)
        summary = self.budget.summarize(combined)
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

    def _verify(self, created_files: list) -> StageResult:
        # Delegate to Judge (US-204)
        return StageResult(stage="verify", success=True, output="Verification pending (Judge not yet implemented)", tokens_used=0)
