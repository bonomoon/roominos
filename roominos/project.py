"""Multi-file project pipeline — process entire legacy projects."""
import os
import re
from dataclasses import dataclass, field
from .pipeline import Pipeline, StageResult
from .llm import LLMClient
from .templates.base import BaseSkill


@dataclass
class FileInfo:
    path: str
    lines: int
    index: str  # from _build_file_index
    dependencies: list[str] = field(default_factory=list)  # #include files


class ProjectPipeline:
    """Process multiple source files as a coordinated project migration."""

    def __init__(self, llm: LLMClient, output_dir: str, template: BaseSkill = None):
        self.llm = llm
        self.output_dir = output_dir
        self.template = template
        self.total_tokens = 0
        self.results: list[dict] = []

    def run(self, source_dir: str) -> list[dict]:
        """Run migration on all source files in a directory."""
        os.makedirs(self.output_dir, exist_ok=True)

        # Phase 1: Index all files
        files = self._index_project(source_dir)
        print(f"  Indexed {len(files)} source files ({sum(f.lines for f in files):,} total lines)")

        # Phase 2: Build dependency order
        ordered = self._dependency_order(files)
        print(f"  Migration order: {' -> '.join(f.path for f in ordered)}")

        # Phase 3: Project-level analysis (1 LLM call)
        project_context = self._analyze_project(ordered)
        self.total_tokens += project_context.tokens_used

        # Phase 4: Per-file migration
        for i, file_info in enumerate(ordered):
            print(f"\n  [{i+1}/{len(ordered)}] Migrating {file_info.path} ({file_info.lines} lines)")
            source_path = os.path.join(source_dir, file_info.path)
            with open(source_path) as f:
                source = f.read()

            file_output = self.output_dir  # All files go to same output
            pipeline = Pipeline(llm=self.llm, output_dir=file_output, template=self.template)

            # Inject project context into the pipeline's analyze
            results = pipeline.run(source, source_path=source_path)
            self.total_tokens += pipeline.total_tokens

            self.results.append({
                "file": file_info.path,
                "lines": file_info.lines,
                "results": [{"stage": r.stage, "success": r.success, "tokens": r.tokens_used} for r in results],
                "score": self._extract_score(results),
                "files_created": len(results[-2].artifacts.get("created_files", [])) if len(results) > 1 else 0,
            })

        return self.results

    def _index_project(self, source_dir: str) -> list[FileInfo]:
        """Index all .pc, .c, .h files in the project."""
        files = []
        for root, _, filenames in os.walk(source_dir):
            for fname in filenames:
                if fname.endswith(('.pc', '.c', '.h')):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, source_dir)
                    with open(full) as f:
                        lines = f.readlines()

                    index = Pipeline._build_file_index([l.rstrip() for l in lines])

                    # Extract #include dependencies
                    deps = []
                    for line in lines:
                        m = re.match(r'#include\s+"([^"]+)"', line)
                        if m:
                            deps.append(m.group(1))

                    files.append(FileInfo(
                        path=rel,
                        lines=len(lines),
                        index=index,
                        dependencies=deps
                    ))
        return files

    def _dependency_order(self, files: list[FileInfo]) -> list[FileInfo]:
        """Topological sort: headers first, then files that depend on them."""
        # Simple: .h files first, then .c/.pc sorted by size (smallest first)
        headers = [f for f in files if f.path.endswith('.h')]
        sources = [f for f in files if not f.path.endswith('.h')]
        sources.sort(key=lambda f: f.lines)
        return headers + sources

    def _analyze_project(self, files: list[FileInfo]) -> StageResult:
        """Single LLM call to understand project architecture."""
        indices = "\n\n".join(f"### {f.path} ({f.lines} lines)\n{f.index}" for f in files)

        system = "You are a software architect analyzing a legacy C/Pro*C project for migration to Java/Spring."
        prompt = (
            f"This project has {len(files)} files. Here are their structural indices:\n\n"
            f"{indices}\n\n"
            f"Describe:\n"
            f"1. Overall architecture (what does this system do?)\n"
            f"2. Data flow between files\n"
            f"3. Shared structs/globals\n"
            f"4. Migration strategy (what order, what depends on what)\n"
            f"Keep it concise — 500 words max."
        )

        resp = self.llm.ask(prompt, system=system)
        return StageResult(stage="project-analyze", success=True, output=resp.content, tokens_used=resp.tokens_used)

    def _extract_score(self, results: list[StageResult]) -> float:
        for r in results:
            if r.stage == "verify" and r.artifacts:
                verdicts = r.artifacts.get("verdicts", [])
                if verdicts:
                    passed = sum(1 for v in verdicts if v.get("passed"))
                    return passed / len(verdicts) * 100
        return 0.0

    def format_report(self) -> str:
        """Format project migration report."""
        lines = ["## Project Migration Report\n"]
        total_score = 0
        total_files = 0

        for r in self.results:
            status = "PASS" if r["score"] >= 75 else "FAIL"
            lines.append(f"{status} {r['file']}: {r['score']:.0f}% ({r['files_created']} Java files)")
            total_score += r["score"]
            total_files += r["files_created"]

        avg = total_score / len(self.results) if self.results else 0
        lines.append(f"\nOverall: {avg:.0f}% average, {total_files} total Java files, {self.total_tokens:,} tokens")
        return "\n".join(lines)
