# ADR-002: Roominos v0.3 — Cutting-Edge Agent Architecture

> **Status**: Proposed
> **Date**: 2026-03-18
> **Context**: v0.2 proves 100% quality but needs speed, multi-file support, and advanced agent capabilities
> **Supersedes**: ADR-001 (extends, not replaces)

## Context

### v0.2 Achievements

Roominos v0.2 (ADR-001) delivered a text-based pipeline orchestrator that eliminated JSON tool-calling failures entirely. The fixed pipeline (ANALYZE -> PLAN -> IMPLEMENT -> VERIFY) with AI-as-a-Judge achieved **7/7 migration scenarios at 100% quality** using the GPT-OSS-20B model.

**Evidence:**
- 98% raw text generation accuracy (50/51 files correct)
- 100% final quality after AI-as-a-Judge retry loop
- Cost: $0.002 per 12-file project (vs $0.02 with Forge+Roo Code)
- Zero JSON structural failures (text-first protocol)

### v0.2 Limitations

Despite perfect quality scores, v0.2 has fundamental architectural limitations that prevent production use:

| Limitation | Evidence | Impact |
|-----------|----------|--------|
| **Speed** | 460 seconds for SETTLE_BAT.pc (1,493 lines) | Unusable for iterative development |
| **Single-file only** | Pipeline processes one source file at a time | Cannot handle multi-file projects |
| **No backtracking** | Linear pipeline: if VERIFY fails 3x, entire run fails | Wasted compute on partial successes |
| **Fixed evaluation** | 8 hardcoded criteria in `MigrationTemplate.get_acceptance_criteria()` | Cannot adapt to arbitrary source code |
| **Simple truncation** | `truncate_context()` at `forge.py:701-729` drops oldest messages | Loses important context indiscriminately |
| **No state persistence** | Pipeline state exists only in memory | Cannot resume after crash |
| **No safety checks** | Generated code is not validated for security/correctness beyond criteria | Risk of producing unsafe code |

### Speed Breakdown (460s for SETTLE_BAT.pc)

Profiling the v0.2 pipeline for the 1,493-line SETTLE_BAT.pc migration reveals that **72% of time is spent in sequential LLM calls during IMPLEMENT and REFLECT**:

```
Stage         Time    LLM Calls    Bottleneck
─────────────────────────────────────────────────
ANALYZE       ~60s    1 call       Source chunking into 8 chunks, sequential processing
PLAN          ~30s    1 call       Single prompt, acceptable
IMPLEMENT    ~200s    22 calls     22 files generated SEQUENTIALLY ← primary bottleneck
REFLECT      ~130s    22 calls     22 files reviewed SEQUENTIALLY ← secondary bottleneck
VERIFY        ~40s    3 calls      Judge + 2 retry calls
─────────────────────────────────────────────────
TOTAL        ~460s    49 calls
```

The IMPLEMENT stage at `pipeline/stages/implement.py` processes files in a `for` loop (ADR-001, lines 228-238 of the architecture spec). Each file gets a fresh context (good for quality) but blocks on the previous file's completion (bad for speed). The same pattern repeats in REFLECT.

### Why v0.3 Now

The v0.2 architecture proved three things:
1. **Text-based interaction works.** Zero JSON failures validates the design.
2. **Fixed pipelines beat agent loops** for weak models (confirming Agentless research).
3. **AI-as-a-Judge is reliable** even with 20B models (classification is easier than generation).

These validated foundations make it safe to add complexity. v0.3 evolves the linear pipeline into a state-machine-driven orchestration system with parallel execution, semantic memory, and pluggable skills.

## Decision

### Architecture Overview

```
                            ┌─────────────────────────────────┐
                            │     Roominos v0.3 Engine        │
                            │                                 │
                            │  ┌───────────────────────────┐  │
                            │  │    State Machine Engine    │  │
                            │  │  (deterministic control)   │  │
                            │  └─────────┬─────────────────┘  │
                            │            │                     │
                            │  ┌─────────▼─────────────────┐  │
                            │  │    Skill Router            │  │
                            │  │  migration │ greenfield    │  │
                            │  │  refactor  │ test-gen      │  │
                            │  │  review    │               │  │
                            │  └─────────┬─────────────────┘  │
                            │            │                     │
                ┌───────────┼────────────┼─────────────┐      │
                │           │            │             │      │
    ┌───────────▼──┐  ┌─────▼────┐  ┌────▼───┐  ┌─────▼──┐  │
    │ Semantic     │  │ Adaptive │  │ Safety │  │ Check- │  │
    │ Memory       │  │ Eval     │  │ Guard  │  │ point  │  │
    │ Manager      │  │ Engine   │  │        │  │ Store  │  │
    └──────────────┘  └──────────┘  └────────┘  └────────┘  │
                            │                                 │
                            │  ┌───────────────────────────┐  │
                            │  │   Multi-File Pipeline     │  │
                            │  │  index → graph → topo →   │  │
                            │  │  migrate → cross-verify   │  │
                            │  └───────────────────────────┘  │
                            └─────────────────────────────────┘
                                          │
                            ┌─────────────▼─────────────────┐
                            │    Text-Based LLM Client      │
                            │  (unchanged from v0.2)        │
                            │  TextLLMClient at llm/client.py│
                            └───────────────────────────────┘
```

### 1. State Machine Engine

v0.2's linear pipeline (`engine.py` runs stages in fixed order) cannot backtrack. When VERIFY fails after 3 retries, the entire run fails and all generated files are lost.

v0.3 replaces the linear sequencing with a formal state machine where **transitions are deterministic** (no LLM decides next state) and **backtracking is bounded** (max depth: 3).

#### State Diagram

```
                    ┌──────────────────────────────────────────────────────┐
                    │                                                      │
                    ▼                                                      │
  ┌──────┐    ┌─────────┐    ┌─────────┐    ┌──────┐    ┌───────────┐   │
  │ INIT │───▶│  INDEX  │───▶│ ANALYZE │───▶│ PLAN │───▶│ IMPLEMENT │───┤
  └──────┘    └─────────┘    └─────────┘    └──────┘    └─────┬─────┘   │
                                                              │          │
                                                              ▼          │
                                                        ┌──────────┐    │
                                                        │ REFLECT  │    │
                                                        └─────┬────┘    │
                                                              │          │
                                            backtrack         ▼          │
                                  ┌───────────────────┌──────────┐      │
                                  │                   │  VERIFY  │      │
                                  │                   └─────┬────┘      │
                                  │                         │            │
                                  │          ┌──────────────┼────────┐  │
                                  │          │ pass         │ fail   │  │
                                  │          ▼              ▼        │  │
                                  │    ┌──────────┐  ┌───────────┐  │  │
                                  │    │ COMPLETE │  │ BACKTRACK │──┘  │
                                  │    └──────────┘  └─────┬─────┘     │
                                  │                        │            │
                                  │                        │ depth > 3  │
                                  │                        ▼            │
                                  │                  ┌──────────┐      │
                                  │                  │  FAILED  │      │
                                  │                  └──────────┘      │
                                  │                                     │
                                  └─── CHECKPOINT saveable at any ──────┘
                                       state transition
```

#### States

| State | Entry Condition | Exit Condition | Artifacts Produced |
|-------|----------------|----------------|-------------------|
| `INIT` | CLI invocation | Config validated | `config.json` |
| `INDEX` | Config valid | All source files indexed | `index.json` (per-file summaries) |
| `ANALYZE` | Index complete | Source semantics extracted | `analysis.json` |
| `PLAN` | Analysis complete | File list with dependencies | `plan.json` |
| `IMPLEMENT` | Plan complete | All files generated | `generated/*.java` |
| `REFLECT` | Implementation complete | Deterministic fixes applied | `reflect_report.json` |
| `VERIFY` | Reflect complete | Judge verdict produced | `judge_report.json` |
| `BACKTRACK` | Verify failed, depth < 3 | Returns to IMPLEMENT with fix instructions | `backtrack_N.json` |
| `CHECKPOINT` | Any state transition | State serialized to disk | `checkpoint_STATE.json` |
| `COMPLETE` | Verify passed | Output files written | `summary.json` |
| `FAILED` | Backtrack depth > 3 | Error report with partial results | `failure_report.json` |

#### Implementation Interface

The state machine replaces the linear `PipelineEngine.run()` method from ADR-001 (architecture spec lines 208-268):

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import json
from pathlib import Path


class State(Enum):
    INIT = "init"
    INDEX = "index"
    ANALYZE = "analyze"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REFLECT = "reflect"
    VERIFY = "verify"
    BACKTRACK = "backtrack"
    CHECKPOINT = "checkpoint"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class Transition:
    from_state: State
    to_state: State
    condition: str  # human-readable condition description
    guard: str      # callable name that returns bool


@dataclass
class PipelineState:
    """Serializable pipeline state for checkpointing."""
    current_state: State = State.INIT
    backtrack_depth: int = 0
    max_backtrack: int = 3
    artifacts: dict = field(default_factory=dict)
    # artifacts keys: "index", "analysis", "plan", "generated_files",
    #                 "reflect_report", "judge_report", "backtrack_history"
    elapsed_seconds: float = 0.0
    llm_call_count: int = 0
    skill_name: str = ""
    checkpoint_path: Optional[str] = None


# Transition table — all transitions are deterministic
TRANSITIONS: list[Transition] = [
    Transition(State.INIT,      State.INDEX,     "config validated",          "config_valid"),
    Transition(State.INDEX,     State.ANALYZE,   "all files indexed",         "index_complete"),
    Transition(State.ANALYZE,   State.PLAN,      "analysis extracted",        "analysis_complete"),
    Transition(State.PLAN,      State.IMPLEMENT, "plan generated",            "plan_complete"),
    Transition(State.IMPLEMENT, State.REFLECT,   "all files generated",       "implement_complete"),
    Transition(State.REFLECT,   State.VERIFY,    "deterministic fixes done",  "reflect_complete"),
    Transition(State.VERIFY,    State.COMPLETE,  "all criteria pass",         "verify_passed"),
    Transition(State.VERIFY,    State.BACKTRACK, "criteria failed, depth<3",  "verify_failed_retriable"),
    Transition(State.VERIFY,    State.FAILED,    "criteria failed, depth>=3", "verify_failed_terminal"),
    Transition(State.BACKTRACK, State.IMPLEMENT, "fix instructions ready",    "backtrack_ready"),
]


class StateMachineEngine:
    """
    Deterministic state machine that replaces v0.2's linear pipeline.

    Key difference from v0.2 PipelineEngine (ADR-001):
    - States are explicit, not implicit in code flow
    - Backtracking is first-class (not a retry loop bolted onto verify)
    - Checkpointing happens at every state transition
    - Each state handler is a separate, testable unit
    """

    def __init__(self, config, skill, llm_client):
        self.config = config
        self.skill = skill
        self.llm = llm_client
        self.state = PipelineState(skill_name=skill.name)
        self._handlers = {
            State.INIT:      self._handle_init,
            State.INDEX:     self._handle_index,
            State.ANALYZE:   self._handle_analyze,
            State.PLAN:      self._handle_plan,
            State.IMPLEMENT: self._handle_implement,
            State.REFLECT:   self._handle_reflect,
            State.VERIFY:    self._handle_verify,
            State.BACKTRACK: self._handle_backtrack,
        }

    async def run(self) -> PipelineState:
        """Execute state machine until COMPLETE or FAILED."""
        while self.state.current_state not in (State.COMPLETE, State.FAILED):
            handler = self._handlers.get(self.state.current_state)
            if not handler:
                raise ValueError(f"No handler for state {self.state.current_state}")

            # Execute current state
            next_state = await handler()

            # Checkpoint at every transition
            self._checkpoint()

            # Transition
            self.state.current_state = next_state

        return self.state

    def _checkpoint(self):
        """Serialize state to disk. Enables resume after crash."""
        if self.config.checkpoint_dir:
            path = Path(self.config.checkpoint_dir) / f"checkpoint_{self.state.current_state.value}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            # PipelineState is fully serializable (no callables, no file handles)
            with open(path, "w") as f:
                json.dump(self._serialize_state(), f, indent=2)
            self.state.checkpoint_path = str(path)

    @classmethod
    def resume(cls, checkpoint_path: str, config, skill, llm_client) -> "StateMachineEngine":
        """Resume from a checkpoint file."""
        with open(checkpoint_path) as f:
            data = json.load(f)
        engine = cls(config, skill, llm_client)
        engine.state = cls._deserialize_state(data)
        return engine
```

#### Backtracking Logic

When VERIFY fails, the state machine enters BACKTRACK which analyzes the judge's failure report and produces targeted fix instructions. Unlike v0.2's simple retry loop (ADR-001, architecture spec lines 249-264), BACKTRACK preserves history of previous attempts to avoid repeating the same fix:

```python
async def _handle_backtrack(self) -> State:
    """
    Analyze verify failures and produce fix instructions for IMPLEMENT.
    Tracks backtrack history to avoid repeating failed fixes.
    """
    self.state.backtrack_depth += 1

    if self.state.backtrack_depth > self.state.max_backtrack:
        return State.FAILED

    judge_report = self.state.artifacts.get("judge_report", {})
    failures = judge_report.get("failures", [])
    history = self.state.artifacts.setdefault("backtrack_history", [])

    # Build fix instructions with anti-repetition context
    fix_instructions = []
    for failure in failures:
        previous_fixes = [
            h["fix_instruction"]
            for h in history
            if h["criterion"] == failure["criterion"]
        ]

        instruction = {
            "criterion": failure["criterion"],
            "reason": failure["reason"],
            "fix_instruction": failure["fix_instruction"],
            "target_file": failure.get("target_file", ""),
            "previous_attempts": previous_fixes,
            "attempt_number": self.state.backtrack_depth,
        }
        fix_instructions.append(instruction)

    # Record this backtrack attempt
    history.append({
        "depth": self.state.backtrack_depth,
        "failures": failures,
        "fix_instructions": fix_instructions,
    })

    self.state.artifacts["fix_instructions"] = fix_instructions
    return State.IMPLEMENT
```

### 2. Speed Optimization Strategy

**Target: 460s -> 120s (3.8x speedup)**

Three independent strategies, each addressing a different bottleneck:

#### Strategy A: Parallel Implementation (IMPLEMENT stage: 200s -> 50s)

The v0.2 IMPLEMENT stage generates files sequentially. Many files are independent (e.g., Entity A and Entity B have no cross-dependency). These can be generated in parallel.

**Dependency analysis from `plan.json`:**
```
pom.xml              → independent (no deps)
Entity A             → depends on pom.xml
Entity B             → depends on pom.xml
Repository A         → depends on Entity A
Repository B         → depends on Entity B
Service              → depends on Repository A, Repository B
Controller           → depends on Service
DTO                  → independent
Config               → independent
Test A               → depends on Service
Test B               → depends on Service
```

**Parallelizable groups** (topologically sorted):
```
Level 0: [pom.xml, DTO, Config]           → 3 files in parallel
Level 1: [Entity A, Entity B]             → 2 files in parallel
Level 2: [Repository A, Repository B]     → 2 files in parallel
Level 3: [Service]                         → 1 file
Level 4: [Controller]                      → 1 file
Level 5: [Test A, Test B]                 → 2 files in parallel
```

**Sequential: 22 calls x ~9s = ~200s**
**Parallel:   6 levels x ~9s = ~54s** (with max concurrency 3)

```python
import asyncio
from collections import defaultdict


async def implement_parallel(
    plan: dict,
    llm: "TextLLMClient",
    config: "RoominosConfig",
    skill: "BaseSkill",
    analysis: dict,
    max_concurrency: int = 3,
) -> list[dict]:
    """
    Execute IMPLEMENT stage with dependency-aware parallelism.

    Replaces the sequential loop in v0.2:
        for i, file_spec in enumerate(plan["files"]):
            result = ImplementStage(...).run(file_spec=file_spec, ...)

    Groups files by dependency level and runs each level in parallel.
    """
    files = plan["files"]
    dep_graph = _build_dependency_graph(files)
    levels = _topological_levels(files, dep_graph)

    generated = []
    semaphore = asyncio.Semaphore(max_concurrency)

    for level_idx, level_files in enumerate(levels):
        # All files in this level can run in parallel
        async def generate_one(file_spec):
            async with semaphore:
                return await ImplementStage(llm, config).run(
                    file_spec=file_spec,
                    analysis=analysis,
                    plan=plan,
                    template=skill,
                    # Pass already-generated files as cross-reference context
                    prior_files=generated,
                )

        level_results = await asyncio.gather(
            *[generate_one(f) for f in level_files]
        )
        generated.extend(level_results)

    return generated


def _build_dependency_graph(files: list[dict]) -> dict[str, set[str]]:
    """Build {file_path: set(dependency_paths)} from plan entries."""
    graph = {}
    for f in files:
        path = f["path"]
        deps = set(f.get("dependencies", []))
        graph[path] = deps
    return graph


def _topological_levels(files: list[dict], graph: dict) -> list[list[dict]]:
    """
    Group files into levels where all dependencies of level N
    are in levels < N. Files within the same level are independent.
    """
    file_map = {f["path"]: f for f in files}
    assigned = set()
    levels = []

    remaining = set(graph.keys())
    while remaining:
        # Find all files whose deps are fully satisfied
        level = []
        for path in list(remaining):
            deps = graph.get(path, set())
            if deps.issubset(assigned):
                level.append(file_map[path])
                remaining.discard(path)

        if not level:
            # Circular dependency — break by picking one arbitrarily
            arbitrary = remaining.pop()
            level.append(file_map[arbitrary])

        for f in level:
            assigned.add(f["path"])
        levels.append(level)

    return levels
```

#### Strategy B: Smart Reflect (REFLECT stage: 130s -> 20s)

The v0.2 REFLECT stage sends every generated file through an LLM review call. For small files (<100 lines) and files that follow templates closely, this is wasteful. Most "reflect" fixes are deterministic (missing imports, wrong annotation names).

```python
import re


class SmartReflect:
    """
    Replace v0.2's LLM-based reflect with a two-tier strategy:
    - Tier 1: Deterministic regex fixes (instant, no LLM call)
    - Tier 2: LLM review only for files > 100 lines or complex logic

    Expected impact: 18 of 22 files handled by Tier 1 (no LLM),
    4 files need Tier 2 (LLM review).
    Tier 1: ~0.1s per file x 18 = ~2s
    Tier 2: ~9s per file x 4 = ~36s (parallel: ~18s)
    Total: ~20s (vs 130s in v0.2)
    """

    # Deterministic fix patterns (no LLM needed)
    DETERMINISTIC_FIXES = [
        # javax -> jakarta (Spring Boot 3.x)
        (r"import javax\.persistence\.", "import jakarta.persistence."),
        (r"import javax\.validation\.",  "import jakarta.validation."),
        # GenerationType.IDENTITY -> SEQUENCE (Oracle)
        (r"GenerationType\.IDENTITY", "GenerationType.SEQUENCE"),
        # double/Double -> BigDecimal for monetary fields
        (r"private\s+[Dd]ouble\s+(balance|amount|price|fee|rate|total|interest|tax)",
         r"private BigDecimal \1"),
        # Missing BigDecimal import
        (r"(import jakarta\.persistence\.\*;)",
         r"\1\nimport java.math.BigDecimal;"),
        # @Table name should be uppercase
        (r'@Table\(name\s*=\s*"([a-z_]+)"\)',
         lambda m: f'@Table(name = "{m.group(1).upper()}")'),
    ]

    def reflect_file(self, path: str, content: str) -> tuple[str, list[str], bool]:
        """
        Apply deterministic fixes to a generated file.

        Returns:
            (fixed_content, list_of_fixes_applied, needs_llm_review)
        """
        fixes_applied = []
        fixed = content

        for pattern, replacement in self.DETERMINISTIC_FIXES:
            if re.search(pattern, fixed):
                fixed = re.sub(pattern, replacement, fixed)
                fixes_applied.append(f"Applied: {pattern[:50]}...")

        # Decide if LLM review is needed
        line_count = len(fixed.split("\n"))
        has_complex_logic = any(kw in fixed for kw in [
            "synchronized", "CompletableFuture", "Stream.of",
            "TransactionTemplate", "savepoint", "CASE WHEN",
        ])
        needs_llm = line_count > 100 or has_complex_logic

        return fixed, fixes_applied, needs_llm
```

#### Strategy C: Analyze Caching (ANALYZE stage: 60s -> 15s)

If the same source file is analyzed twice (common during development iteration), the cached analysis result is reused. Cache key is a hash of (source_content + skill_name + analyze_prompt_version).

```python
import hashlib
from pathlib import Path


class AnalyzeCache:
    """
    Cache analysis results keyed by content hash.
    Same source file + same skill -> same analysis.

    Cache location: .roominos/cache/analyze/
    """

    def __init__(self, cache_dir: str = ".roominos/cache/analyze"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_key(self, source_content: str, skill_name: str, prompt_version: str) -> str:
        """Deterministic hash of inputs that affect analysis output."""
        hasher = hashlib.sha256()
        hasher.update(source_content.encode())
        hasher.update(skill_name.encode())
        hasher.update(prompt_version.encode())
        return hasher.hexdigest()[:16]

    def get(self, key: str) -> dict | None:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            import json
            with open(path) as f:
                return json.load(f)
        return None

    def put(self, key: str, analysis: dict) -> None:
        import json
        path = self.cache_dir / f"{key}.json"
        with open(path, "w") as f:
            json.dump(analysis, f, indent=2)
```

#### Combined Speed Target

```
Stage         v0.2    v0.3 Target    Strategy
──────────────────────────────────────────────────
ANALYZE       ~60s    ~15s           Caching + shorter prompts
PLAN          ~30s    ~15s           Shorter prompts, structured output
IMPLEMENT    ~200s    ~50s           Parallel execution (3 concurrent)
REFLECT      ~130s    ~20s           Deterministic tier (18/22 files)
VERIFY        ~40s    ~20s           Single call, no retry if Reflect fixes applied
──────────────────────────────────────────────────
TOTAL        ~460s   ~120s           3.8x speedup
LLM Calls      49     ~15            70% reduction
```

### 3. Skill System

v0.2 has a single `MigrationTemplate` class (ADR-001, architecture spec lines 835-918) that hardcodes Pro*C-to-Java knowledge. v0.3 extracts this into a pluggable skill architecture where each skill provides domain-specific prompts, evaluation criteria, and file generation patterns.

#### Skill Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SkillManifest:
    """Metadata for skill discovery and routing."""
    name: str                          # e.g., "proc-to-java"
    description: str                   # human-readable
    source_patterns: list[str]         # glob patterns: ["*.pc", "*.c"]
    target_patterns: list[str]         # glob patterns: ["*.java", "*.xml"]
    mandatory_files: list[str]         # files always generated: ["pom.xml"]
    prompt_version: str                # for cache invalidation


class BaseSkill(ABC):
    """
    Pluggable skill interface. Each skill encodes domain knowledge
    that the LLM lacks or produces unreliably.

    Skills are loaded from roominos/skills/<name>.py and registered
    via the manifest.

    Current skill set from v0.2 Roo rules:
    - .roo/rules-coder/02-java-spring.md -> MigrationSkill.system_prompt
    - .roo/rules-reviewer/02-migration-checks.md -> MigrationSkill.get_acceptance_criteria()
    - demos/migration/task_*/verification.md -> MigrationSkill criteria templates
    """

    @abstractmethod
    def manifest(self) -> SkillManifest:
        """Return skill metadata."""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """System prompt injected into every LLM call for this skill."""
        ...

    @abstractmethod
    def get_analyze_prompt(self, source_chunk: str) -> str:
        """Prompt for ANALYZE stage. Extracts domain-specific information."""
        ...

    @abstractmethod
    def get_plan_prompt(self, analysis: dict) -> str:
        """Prompt for PLAN stage. Produces ordered file list."""
        ...

    @abstractmethod
    def get_implement_prompt(self, file_spec: dict, analysis: dict,
                             prior_files: list[dict]) -> str:
        """Prompt for IMPLEMENT stage. Generates one file."""
        ...

    @abstractmethod
    def get_acceptance_criteria(self, analysis: dict) -> list[str]:
        """
        Generate evaluation criteria FROM the source analysis.
        Replaces v0.2's fixed 8 criteria with adaptive criteria.
        See Section 6 (Adaptive Eval) for the generation algorithm.
        """
        ...

    @abstractmethod
    def get_verify_prompt(self, files: list[dict], criteria: list[str]) -> str:
        """Prompt for VERIFY stage (AI-as-a-Judge)."""
        ...

    def get_mandatory_files(self) -> list[str]:
        """Files that must always be generated regardless of source."""
        return self.manifest().mandatory_files
```

#### Concrete Skills

```python
class MigrationSkill(BaseSkill):
    """
    Pro*C to Java/Spring migration.

    Domain knowledge sources:
    - .roo/rules-coder/02-java-spring.md (Oracle-specific rules)
    - .roo/rules-reviewer/02-migration-checks.md (equivalence checks)
    - demos/migration/task_010_complex_batch/verification.md (134 criteria)
    """

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="proc-to-java",
            description="Migrate Pro*C (C with Embedded SQL) to Java/Spring Boot",
            source_patterns=["*.pc", "*.h"],
            target_patterns=["*.java", "*.xml", "*.yml"],
            mandatory_files=["pom.xml", "application.yml", "application-test.yml"],
            prompt_version="2026.03.18",
        )

    def get_system_prompt(self) -> str:
        # Extracted from .roo/rules-coder/02-java-spring.md
        return """You are migrating Pro*C (C with Embedded SQL) to Java/Spring Boot 3.
MANDATORY RULES:
- jakarta.persistence (NOT javax.persistence)
- @SequenceGenerator for Oracle (NEVER GenerationType.IDENTITY)
- BigDecimal for ALL monetary/numeric fields (NEVER Double/double)
- @Transactional boundaries must match EXEC SQL COMMIT locations
- WHENEVER SQLERROR -> try/catch with specific exception types
- NUMBER(p,s) -> BigDecimal, VARCHAR2(n) -> String with @Size(max=n)
- DATE -> LocalDateTime (Oracle DATE includes time)
OUTPUT FORMAT: Use FILE: marker to create files."""


class GreenfieldSkill(BaseSkill):
    """New project from specification (CRUD API, batch processing, etc.)."""

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="spring-crud",
            description="Generate Spring Boot CRUD API from specification",
            source_patterns=[],  # no source files — spec-driven
            target_patterns=["*.java", "*.xml", "*.yml"],
            mandatory_files=["pom.xml", "application.yml"],
            prompt_version="2026.03.18",
        )


class RefactorSkill(BaseSkill):
    """Legacy modernization (e.g., Java 8 -> 17, Spring 4 -> 6)."""

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="java-modernize",
            description="Modernize legacy Java code (upgrade JDK, Spring, patterns)",
            source_patterns=["*.java"],
            target_patterns=["*.java"],
            mandatory_files=[],
            prompt_version="2026.03.18",
        )


class TestGenSkill(BaseSkill):
    """Generate tests for existing code."""

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="test-gen",
            description="Generate unit and integration tests for existing code",
            source_patterns=["*.java", "*.py"],
            target_patterns=["*Test.java", "test_*.py"],
            mandatory_files=[],
            prompt_version="2026.03.18",
        )


class ReviewSkill(BaseSkill):
    """Code review with structured findings (mirrors Reviewer mode from .roo/rules-reviewer/)."""

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="review",
            description="Structured code review with severity-rated findings",
            source_patterns=["*.java", "*.py", "*.c", "*.pc"],
            target_patterns=[],  # produces report, not code
            mandatory_files=[],
            prompt_version="2026.03.18",
        )
```

#### Skill Discovery and Registration

```python
from pathlib import Path
import importlib


class SkillRegistry:
    """
    Discover and load skills from roominos/skills/ directory.

    Usage:
        registry = SkillRegistry()
        registry.discover("roominos/skills/")
        skill = registry.get("proc-to-java")
    """

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        manifest = skill.manifest()
        self._skills[manifest.name] = skill

    def get(self, name: str) -> BaseSkill:
        if name not in self._skills:
            available = ", ".join(self._skills.keys())
            raise ValueError(f"Unknown skill: {name!r}. Available: {available}")
        return self._skills[name]

    def discover(self, skills_dir: str) -> None:
        """Auto-discover skill classes from Python modules in skills_dir."""
        for py_file in Path(skills_dir).glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            module_name = py_file.stem
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr in dir(module):
                obj = getattr(module, attr)
                if (isinstance(obj, type) and issubclass(obj, BaseSkill)
                        and obj is not BaseSkill):
                    self.register(obj())

    def list_skills(self) -> list[SkillManifest]:
        return [s.manifest() for s in self._skills.values()]
```

### 4. Multi-File Pipeline

v0.2 processes a single source file. Real projects have dozens of files with cross-file dependencies (`#include`, function calls, shared types). v0.3 adds a project-level pipeline that indexes all files, builds a dependency graph, and migrates in topological order with cross-file context.

#### Phase Architecture

```
Phase 1: INDEX (parallel, regex-based)
  Input:  Project directory
  Output: index.json — per-file summary (~1k tokens each)
  Method: Regex extraction (no LLM) for fast structural indexing
          LLM only for semantic understanding of complex files

Phase 2: DEPENDENCY GRAPH (deterministic)
  Input:  index.json
  Output: graph.json — {file: [depends_on_files]}
  Method: Parse #include, function declarations/calls, type references
          No LLM needed — pure static analysis

Phase 3: TOPOLOGICAL SORT (deterministic)
  Input:  graph.json
  Output: migration_order.json — ordered list with parallelizable groups
  Method: Kahn's algorithm with level grouping (same as Section 2 Strategy A)

Phase 4: PER-FILE MIGRATE (parallel within levels)
  Input:  migration_order.json + index.json (cross-file context)
  Output: generated files
  Method: For each file: ANALYZE -> PLAN -> IMPLEMENT using skill prompts
          Cross-file context injected from index.json (not full file content)

Phase 5: CROSS-FILE VERIFY (single LLM call)
  Input:  All generated files + cross-file criteria
  Output: cross_verify_report.json
  Method: Check import consistency, interface matching, type compatibility
```

#### File Indexer

```python
import re
from dataclasses import dataclass


@dataclass
class FileIndex:
    """Lightweight summary of a source file (~1k tokens)."""
    path: str
    language: str           # "c", "proc", "java", "header"
    line_count: int
    functions: list[str]    # function names
    types: list[str]        # struct/class names
    includes: list[str]     # #include / import targets
    sql_statements: list[str]  # EXEC SQL summaries (Pro*C only)
    exports: list[str]      # externally-visible symbols
    imports: list[str]      # symbols used from other files


class ProjectIndexer:
    """
    Fast structural indexing using regex (no LLM).

    For a 50-file project:
    - Index time: ~2s (regex only)
    - Index size: ~50k tokens (50 files x ~1k each)
    - Fits within a single LLM context window for cross-file verification
    """

    def index_file(self, path: str, content: str) -> FileIndex:
        language = self._detect_language(path)

        if language == "proc":
            return self._index_proc(path, content)
        elif language == "c":
            return self._index_c(path, content)
        elif language == "java":
            return self._index_java(path, content)
        elif language == "header":
            return self._index_header(path, content)
        else:
            return FileIndex(path=path, language=language,
                             line_count=len(content.split("\n")),
                             functions=[], types=[], includes=[],
                             sql_statements=[], exports=[], imports=[])

    def _index_proc(self, path: str, content: str) -> FileIndex:
        """Extract Pro*C-specific information via regex."""
        functions = re.findall(r'^(?:void|int|char|double|long)\s+(\w+)\s*\(', content, re.MULTILINE)
        includes = re.findall(r'^#include\s+[<"](.+?)[>"]', content, re.MULTILINE)
        exec_sql = re.findall(r'EXEC\s+SQL\s+(.+?);', content, re.DOTALL | re.IGNORECASE)
        sql_summaries = [s.strip()[:80] for s in exec_sql]

        # Host variables: EXEC SQL BEGIN DECLARE SECTION ... END DECLARE SECTION
        host_vars = re.findall(
            r'EXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION.*?EXEC\s+SQL\s+END\s+DECLARE\s+SECTION',
            content, re.DOTALL | re.IGNORECASE
        )
        types = []
        for section in host_vars:
            structs = re.findall(r'struct\s+(\w+)', section)
            types.extend(structs)

        return FileIndex(
            path=path, language="proc",
            line_count=len(content.split("\n")),
            functions=functions, types=types, includes=includes,
            sql_statements=sql_summaries, exports=functions, imports=[],
        )

    def index_project(self, project_dir: str, patterns: list[str]) -> list[FileIndex]:
        """Index all matching files in a project directory."""
        from pathlib import Path
        indices = []
        for pattern in patterns:
            for file_path in Path(project_dir).glob(pattern):
                content = file_path.read_text(errors="replace")
                index = self.index_file(str(file_path), content)
                indices.append(index)
        return indices
```

### 5. Semantic Memory Manager

v0.2 uses simple truncation for context management: `truncate_context()` at `forge.py:701-729` drops oldest messages, and `limit_tool_results()` at `forge.py:540-587` truncates large tool results by keeping first/last 50 lines. This loses important context indiscriminately.

v0.3 replaces this with importance-scored context selection.

#### Importance Scoring Algorithm

```python
from dataclasses import dataclass


@dataclass
class ContextItem:
    """A piece of context with importance metadata."""
    content: str
    source: str          # e.g., "analysis", "plan", "prior_file", "fix_instruction"
    tokens: int          # estimated token count
    importance: float    # 0.0 to 1.0
    recency: float       # 0.0 (oldest) to 1.0 (newest)
    relevance: float     # 0.0 to 1.0 (to current task)


class SemanticMemoryManager:
    """
    Importance-scored context selection.

    Replaces v0.2's truncation strategies:
    - forge.py:540-587 (limit_tool_results: head/tail truncation)
    - forge.py:594-644 (summarize_old_turns: 1-line summaries)
    - forge.py:701-729 (truncate_context: drop oldest messages)

    Key insight: not all context is equally valuable. A fix instruction
    from BACKTRACK is more important than a successful file generation.
    The analysis of the current file is more relevant than a prior file's
    analysis.
    """

    # Importance weights by source type
    SOURCE_WEIGHTS = {
        "system_prompt":    1.0,    # always include
        "fix_instruction":  0.95,   # critical for backtracking
        "current_analysis": 0.90,   # directly relevant
        "plan_entry":       0.85,   # current file's plan
        "acceptance_criteria": 0.80, # judge needs these
        "prior_file":       0.50,   # cross-reference, lower priority
        "prior_analysis":   0.40,   # background context
        "conversation":     0.30,   # historical turns
    }

    def __init__(self, max_tokens: int = 15000):
        self.max_tokens = max_tokens
        self.items: list[ContextItem] = []

    def add(self, content: str, source: str, relevance: float = 0.5) -> None:
        """Add a context item with automatic importance scoring."""
        tokens = len(content) // 4  # rough estimate
        base_weight = self.SOURCE_WEIGHTS.get(source, 0.3)
        recency = len(self.items) / max(len(self.items) + 1, 1)
        importance = base_weight * 0.6 + relevance * 0.3 + recency * 0.1

        self.items.append(ContextItem(
            content=content,
            source=source,
            tokens=tokens,
            importance=importance,
            recency=recency,
            relevance=relevance,
        ))

    def select(self) -> list[ContextItem]:
        """
        Select context items that fit within budget, prioritized by importance.

        Algorithm:
        1. Sort by importance (descending)
        2. Greedily include items until budget exhausted
        3. For items that don't fit: try summarizing (50% token reduction)
        4. Return selected items in original insertion order
        """
        sorted_items = sorted(self.items, key=lambda x: -x.importance)

        selected = []
        remaining_tokens = self.max_tokens

        for item in sorted_items:
            if item.tokens <= remaining_tokens:
                selected.append(item)
                remaining_tokens -= item.tokens
            elif item.importance > 0.7 and item.tokens > 500:
                # High-importance item that doesn't fit: summarize it
                summarized = self._summarize(item)
                if summarized.tokens <= remaining_tokens:
                    selected.append(summarized)
                    remaining_tokens -= summarized.tokens

        # Return in original order (not importance order)
        original_order = {id(item): i for i, item in enumerate(self.items)}
        selected.sort(key=lambda x: original_order.get(id(x), float("inf")))

        return selected

    def _summarize(self, item: ContextItem) -> ContextItem:
        """Compress a context item to ~50% of its original size."""
        lines = item.content.split("\n")
        if len(lines) <= 10:
            return item  # too short to summarize

        # Keep first 3 and last 3 lines, summarize middle
        head = "\n".join(lines[:3])
        tail = "\n".join(lines[-3:])
        summary = f"{head}\n[... {len(lines) - 6} lines summarized ...]\n{tail}"

        return ContextItem(
            content=summary,
            source=item.source,
            tokens=len(summary) // 4,
            importance=item.importance * 0.9,  # slight penalty for summarization
            recency=item.recency,
            relevance=item.relevance,
        )

    def build_prompt(self) -> str:
        """Build the final prompt from selected context items."""
        selected = self.select()
        return "\n\n".join(item.content for item in selected)
```

### 6. Adaptive Evaluation

v0.2 uses fixed acceptance criteria hardcoded in `MigrationTemplate.get_acceptance_criteria()` (ADR-001, architecture spec lines 869-879). These 8 criteria are the same regardless of source complexity — a simple SELECT migration gets the same criteria as a 1,493-line batch settlement system with 134 verification items (see `demos/migration/task_010_complex_batch/verification.md`).

v0.3 generates criteria dynamically from the source analysis.

```python
class AdaptiveEvalEngine:
    """
    Generate evaluation criteria FROM source code analysis.

    Replaces the fixed 8 criteria in v0.2's MigrationTemplate with
    criteria that scale with source complexity.

    Algorithm:
    1. Parse analysis.json for constructs found
    2. For each construct type, generate specific criteria
    3. Weight criteria by construct complexity
    4. Cap total criteria at budget (max ~50 for judge prompt to fit in context)

    Example:
      Source has 3 EXEC SQL SELECT -> generates 3 SQL equivalence criteria
      Source has 5 EXEC SQL INSERT -> generates 5 INSERT mapping criteria
      Source has SAVEPOINT -> generates transaction boundary criterion
      Source has no cursors -> no cursor criteria generated
    """

    # Criterion templates keyed by construct type
    CRITERION_TEMPLATES = {
        "exec_sql_select": "EXEC SQL SELECT at line {line} ({summary}) mapped to JPA method or @Query",
        "exec_sql_insert": "EXEC SQL INSERT at line {line} ({table}) mapped to repository.save() or jdbcTemplate",
        "exec_sql_update": "EXEC SQL UPDATE at line {line} ({table}) mapped to @Modifying @Query or entity setter",
        "exec_sql_delete": "EXEC SQL DELETE at line {line} ({table}) mapped to repository.delete()",
        "cursor_declare":  "Cursor {name} mapped to List<T> or Stream<T> return type",
        "host_variable":   "Host variable {name} ({c_type}) mapped to correct Java type",
        "indicator_var":   "Indicator variable for {host_var} mapped to nullable type with null check",
        "commit":          "@Transactional boundary matches COMMIT at line {line}",
        "savepoint":       "SAVEPOINT {name} mapped to programmatic savepoint or nested transaction",
        "whenever_error":  "WHENEVER SQLERROR at line {line} mapped to try/catch block",
        "whenever_notfound": "WHENEVER NOT FOUND at line {line} mapped to empty result handling",
        "function":        "Function {name} (lines {start}-{end}) has corresponding Java method",
        "numeric_field":   "Numeric field {name} uses BigDecimal (not double)",
        "date_field":      "Date field {name} uses LocalDateTime",
        "sequence":        "Entity uses @SequenceGenerator (not IDENTITY)",
    }

    def generate_criteria(self, analysis: dict, max_criteria: int = 50) -> list[dict]:
        """
        Generate criteria from analysis.json.

        analysis structure (from ANALYZE stage):
        {
            "functions": [{"name": "main", "line_start": 1, "line_end": 50}],
            "exec_sql": [{"type": "SELECT", "line": 42, "summary": "..."}],
            "host_variables": [{"name": "acct_no", "c_type": "char[20]"}],
            "indicators": [{"host_var": "balance", "line": 15}],
            "error_handling": [{"type": "WHENEVER SQLERROR", "line": 5}],
            "transactions": [{"type": "COMMIT", "line": 120}],
        }
        """
        criteria = []

        # Always include universal criteria
        criteria.append({
            "text": "Entity uses @SequenceGenerator (not IDENTITY) for Oracle",
            "weight": 1.0,
            "category": "infrastructure",
        })
        criteria.append({
            "text": "Uses jakarta.persistence (not javax.persistence) for Spring Boot 3.x",
            "weight": 1.0,
            "category": "infrastructure",
        })

        # Generate from SQL statements
        for sql in analysis.get("exec_sql", []):
            sql_type = sql.get("type", "").upper()
            template_key = f"exec_sql_{sql_type.lower()}"
            if template_key in self.CRITERION_TEMPLATES:
                text = self.CRITERION_TEMPLATES[template_key].format(**sql)
                criteria.append({"text": text, "weight": 0.8, "category": "sql_equivalence"})

        # Generate from host variables
        for hv in analysis.get("host_variables", []):
            if any(kw in hv.get("c_type", "").lower() for kw in ["double", "float", "comp"]):
                text = self.CRITERION_TEMPLATES["numeric_field"].format(name=hv["name"])
                criteria.append({"text": text, "weight": 0.9, "category": "data_type"})

        # Generate from error handling
        for eh in analysis.get("error_handling", []):
            eh_type = eh.get("type", "").replace(" ", "_").lower()
            template_key = eh_type if eh_type in self.CRITERION_TEMPLATES else None
            if template_key:
                text = self.CRITERION_TEMPLATES[template_key].format(**eh)
                criteria.append({"text": text, "weight": 0.7, "category": "error_handling"})

        # Generate from transactions
        for tx in analysis.get("transactions", []):
            tx_type = tx.get("type", "").lower()
            if tx_type in self.CRITERION_TEMPLATES:
                text = self.CRITERION_TEMPLATES[tx_type].format(**tx)
                criteria.append({"text": text, "weight": 0.85, "category": "transaction"})

        # Cap at budget (sorted by weight descending)
        criteria.sort(key=lambda c: -c["weight"])
        return criteria[:max_criteria]
```

### 7. Checkpointing

v0.2 has no state persistence. If the process crashes during IMPLEMENT (which takes ~200s), all progress is lost. v0.3 saves pipeline state at every state transition, enabling resume-from-checkpoint.

#### Checkpoint Format

```json
{
  "version": "0.3.0",
  "timestamp": "2026-03-18T14:30:00",
  "state": "implement",
  "backtrack_depth": 0,
  "skill": "proc-to-java",
  "config": {
    "source": "SETTLE_BAT.pc",
    "output": "java-migration/",
    "api_url": "http://localhost:11434/v1",
    "model": "gpt-oss-20b"
  },
  "artifacts": {
    "index": { "file_count": 1, "total_lines": 1493 },
    "analysis": { "functions": 12, "exec_sql": 47, "host_vars": 35 },
    "plan": { "file_count": 22, "levels": 6 },
    "generated_files": [
      { "path": "pom.xml", "status": "complete", "lines": 45 },
      { "path": "src/.../Entity.java", "status": "complete", "lines": 120 },
      { "path": "src/.../Repository.java", "status": "in_progress", "lines": 0 }
    ]
  },
  "metrics": {
    "elapsed_seconds": 145.2,
    "llm_call_count": 8,
    "tokens_used": 42000
  }
}
```

#### Resume Protocol

```python
# Resume after crash:
#   roominos migrate --resume .roominos/checkpoint_implement.json

# The engine:
# 1. Loads checkpoint state
# 2. Identifies which files in IMPLEMENT were completed
# 3. Skips completed files, resumes from the first incomplete file
# 4. Continues the state machine from the checkpointed state
```

### 8. Clarification Behavior

v0.2 never asks the user anything — it runs the full pipeline silently. v0.3 adds ambiguity detection that can pause the pipeline and request clarification.

```python
class ClarificationDetector:
    """
    Detect ambiguity in source code or user instructions
    that requires human input before proceeding.

    Triggers:
    - Multiple possible interpretations of business logic
    - Commented-out code that might be intentional or a bug
    - Hardcoded values that might be configuration
    - Unclear transaction boundaries

    Behavior modes:
    - interactive: pause and ask user (default for CLI)
    - batch: log ambiguity and make best-guess choice (for CI/CD)
    - strict: fail on any ambiguity (for high-stakes migrations)
    """

    AMBIGUITY_PATTERNS = [
        {
            "pattern": r"//\s*TODO|//\s*FIXME|//\s*HACK|//\s*XXX",
            "question": "Found TODO/FIXME comment at {file}:{line}. Should the migrated code address this, preserve it as-is, or remove it?",
            "severity": "medium",
        },
        {
            "pattern": r"/\*.*?commented.*?out.*?\*/",
            "question": "Found commented-out code at {file}:{line}. Is this dead code to remove, or temporarily disabled logic to preserve?",
            "severity": "high",
        },
        {
            "pattern": r'(?:password|passwd|secret|key)\s*=\s*["\']',
            "question": "Found hardcoded credential at {file}:{line}. Should this be externalized to configuration?",
            "severity": "critical",
        },
        {
            "pattern": r"EXEC\s+SQL\s+COMMIT.*EXEC\s+SQL\s+COMMIT",
            "question": "Found multiple COMMIT statements. Should these be separate @Transactional methods or a single transaction with savepoints?",
            "severity": "high",
        },
    ]

    def detect(self, source: str, file_path: str, mode: str = "interactive") -> list[dict]:
        """Scan source for ambiguities that need human input."""
        import re
        ambiguities = []
        for ap in self.AMBIGUITY_PATTERNS:
            for match in re.finditer(ap["pattern"], source, re.DOTALL | re.IGNORECASE):
                line = source[:match.start()].count("\n") + 1
                ambiguities.append({
                    "file": file_path,
                    "line": line,
                    "question": ap["question"].format(file=file_path, line=line),
                    "severity": ap["severity"],
                    "context": source[max(0, match.start()-100):match.end()+100],
                })

        if mode == "batch":
            # Log ambiguities but don't block
            for a in ambiguities:
                print(f"[AMBIGUITY] {a['severity']}: {a['question']}")
            return []  # proceed without blocking
        elif mode == "strict":
            if ambiguities:
                raise AmbiguityError(ambiguities)

        return ambiguities  # interactive mode: caller presents to user
```

### 9. Safety Reasoning

v0.2 has no safety validation beyond the AI-as-a-Judge criteria. v0.3 adds policy-based constraints that catch unsafe patterns before files are written to disk.

```python
import re


class SafetyGuard:
    """
    Policy-based safety constraints on generated code.

    Applied AFTER IMPLEMENT and BEFORE writing files to disk.
    These are deterministic checks (no LLM) that catch common
    security and correctness issues.

    Sources:
    - .roo/rules-reviewer/01-guidelines.md (security checks)
    - .roo/rules-reviewer/02-migration-checks.md (SQL injection)
    - OWASP Top 10 patterns
    """

    POLICIES = [
        {
            "name": "no_sql_injection",
            "description": "Prevent string concatenation in SQL queries",
            "pattern": r'(?:\"SELECT|\"INSERT|\"UPDATE|\"DELETE).*?\+\s*\w+',
            "severity": "critical",
            "fix_hint": "Use parameterized queries (@Param) instead of string concatenation",
        },
        {
            "name": "no_hardcoded_credentials",
            "description": "Prevent hardcoded passwords and secrets",
            "pattern": r'(?:password|secret|api[_-]?key)\s*=\s*"[^"]{3,}"',
            "severity": "critical",
            "fix_hint": "Use @Value('${property}') or environment variable injection",
        },
        {
            "name": "no_system_exit",
            "description": "Prevent System.exit() in library/service code",
            "pattern": r'System\.exit\s*\(',
            "severity": "warning",
            "fix_hint": "Throw an exception instead of System.exit()",
        },
        {
            "name": "no_print_statements",
            "description": "Use proper logging instead of System.out/err",
            "pattern": r'System\.(out|err)\.(print|println)\s*\(',
            "severity": "info",
            "fix_hint": "Use SLF4J Logger: log.info(), log.error()",
        },
        {
            "name": "no_raw_exception_catch",
            "description": "Avoid catching generic Exception",
            "pattern": r'catch\s*\(\s*Exception\s+\w+\s*\)',
            "severity": "warning",
            "fix_hint": "Catch specific exception types (DataAccessException, etc.)",
        },
        {
            "name": "no_double_for_money",
            "description": "Monetary fields must use BigDecimal",
            "pattern": r'private\s+(?:double|Double|float|Float)\s+(?:balance|amount|price|fee|rate|total|interest|tax|cost|salary|payment)',
            "severity": "critical",
            "fix_hint": "Use BigDecimal for monetary calculations to avoid precision loss",
        },
        {
            "name": "no_identity_for_oracle",
            "description": "Oracle requires SEQUENCE, not IDENTITY",
            "pattern": r'GenerationType\.IDENTITY',
            "severity": "critical",
            "fix_hint": "Use GenerationType.SEQUENCE with @SequenceGenerator for Oracle",
        },
    ]

    def check(self, path: str, content: str) -> list[dict]:
        """Run all safety policies against a generated file."""
        violations = []
        for policy in self.POLICIES:
            matches = list(re.finditer(policy["pattern"], content, re.IGNORECASE))
            for match in matches:
                line = content[:match.start()].count("\n") + 1
                violations.append({
                    "policy": policy["name"],
                    "severity": policy["severity"],
                    "file": path,
                    "line": line,
                    "match": match.group(0)[:100],
                    "fix_hint": policy["fix_hint"],
                    "description": policy["description"],
                })
        return violations

    def check_all(self, files: list[dict]) -> list[dict]:
        """Check all generated files. Returns list of violations."""
        all_violations = []
        for f in files:
            violations = self.check(f["path"], f["content"])
            all_violations.extend(violations)
        return all_violations

    def has_critical(self, violations: list[dict]) -> bool:
        """Return True if any critical violation exists."""
        return any(v["severity"] == "critical" for v in violations)
```

### 10. Long-Horizon Reliability

v0.2's pipeline can run for 460+ seconds with 49+ LLM calls. Over long runs, state can become corrupted: accumulated context drift, stale references, or inconsistent artifacts. v0.3 adds integrity checks.

```python
import hashlib
import json


class StateIntegrityChecker:
    """
    Detect and recover from state corruption during long pipeline runs.

    Corruption sources:
    - LLM hallucinating file paths that don't match the plan
    - Artifact references becoming stale after backtracking
    - Context window overflow silently truncating important data
    - Concurrent writes to shared state (parallel IMPLEMENT)

    Detection strategy: hash-chain of artifacts.
    Each artifact includes the hash of its predecessor, forming a chain.
    If a hash doesn't match, the chain is broken and we know which
    artifact was corrupted.
    """

    def __init__(self):
        self._hash_chain: list[str] = []

    def record_artifact(self, artifact_name: str, artifact_data: dict) -> str:
        """Record an artifact and return its chain hash."""
        prev_hash = self._hash_chain[-1] if self._hash_chain else "genesis"
        content = json.dumps(artifact_data, sort_keys=True)
        chain_hash = hashlib.sha256(f"{prev_hash}:{content}".encode()).hexdigest()[:16]
        self._hash_chain.append(chain_hash)
        return chain_hash

    def verify_chain(self, artifacts: list[tuple[str, dict]]) -> list[str]:
        """Verify the artifact chain. Returns list of broken links."""
        broken = []
        prev_hash = "genesis"
        for name, data in artifacts:
            content = json.dumps(data, sort_keys=True)
            expected = hashlib.sha256(f"{prev_hash}:{content}".encode()).hexdigest()[:16]
            if self._hash_chain and expected != self._hash_chain[len(broken)]:
                broken.append(name)
            prev_hash = expected
        return broken


class PlanConsistencyChecker:
    """
    Verify that generated files match the plan.

    Detects:
    - Files in plan but not generated
    - Files generated but not in plan (hallucinated paths)
    - Import references to non-existent files
    - Type references that don't match any generated class
    """

    def check(self, plan: dict, generated_files: list[dict]) -> list[dict]:
        issues = []
        planned_paths = {f["path"] for f in plan.get("files", [])}
        generated_paths = {f["path"] for f in generated_files}

        # Missing files
        for path in planned_paths - generated_paths:
            issues.append({
                "type": "missing_file",
                "severity": "critical",
                "path": path,
                "message": f"Planned file not generated: {path}",
            })

        # Hallucinated files
        for path in generated_paths - planned_paths:
            issues.append({
                "type": "unplanned_file",
                "severity": "warning",
                "path": path,
                "message": f"File generated but not in plan: {path}",
            })

        # Import consistency (Java-specific)
        import re
        class_map = {}
        for f in generated_files:
            classes = re.findall(r'public\s+(?:class|interface|enum)\s+(\w+)', f.get("content", ""))
            for cls in classes:
                class_map[cls] = f["path"]

        for f in generated_files:
            content = f.get("content", "")
            imports = re.findall(r'import\s+[\w.]+\.(\w+)\s*;', content)
            for imp in imports:
                # Skip standard library imports
                if imp in class_map or imp[0].islower():
                    continue
                # Check if it's a project class that should exist
                if any(imp in path for path in planned_paths):
                    if imp not in class_map:
                        issues.append({
                            "type": "broken_import",
                            "severity": "warning",
                            "path": f["path"],
                            "message": f"Imports {imp} but no generated class matches",
                        })

        return issues
```

### 11. 20,000+ Line Support

v0.2's `FileChunker` (ADR-001, architecture spec lines 793-828) handles single files up to ~1,500 lines. For projects with 50+ files totaling 20,000+ lines, a different strategy is needed: **module-level decomposition** with incremental migration.

#### Architecture

```
20k+ Line Project
       │
       ▼
┌─────────────────────┐
│  Module Splitter     │  Group related files into migration units
│  (dependency-aware)  │  (~5-10 files per module, ~2-3k lines each)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Project Memory      │  Track: what's migrated, what's pending,
│  (persistent state)  │  cross-module dependencies, interface contracts
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Incremental Engine  │  Migrate one module -> verify -> next module
│  (module-by-module)  │  Each module gets its own state machine run
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Cross-Module Verify │  Check interfaces, imports, types across all
│  (final pass)        │  migrated modules
└─────────────────────┘
```

#### Project Memory

```python
@dataclass
class ProjectMemory:
    """
    Persistent state for multi-module migration projects.

    Survives across multiple CLI invocations. Stored as JSON
    in .roominos/project_memory.json.

    Token budget for full project context:
    - File index: ~1k tokens per file x 50 files = ~50k tokens
    - Module summaries: ~500 tokens per module x 10 modules = ~5k tokens
    - Interface contracts: ~200 tokens per interface x 20 = ~4k tokens
    - Total: ~59k tokens (fits in a single 80k context window)
    """
    project_name: str
    total_files: int
    total_lines: int
    modules: list[dict]             # [{name, files, status, dependencies}]
    migrated_modules: list[str]     # names of completed modules
    pending_modules: list[str]      # names of remaining modules
    interface_contracts: list[dict]  # [{module, exports, imports}]
    known_issues: list[dict]        # [{module, issue, severity}]
    metrics: dict                   # {total_time, total_calls, total_tokens}


class ModuleSplitter:
    """
    Group files into migration modules based on dependency clustering.

    Algorithm:
    1. Build dependency graph from ProjectIndexer output
    2. Find strongly connected components (files that reference each other)
    3. Group SCCs into modules of ~5-10 files each
    4. Order modules by dependency (leaf modules first)

    Constraint: each module must fit within a single pipeline run
    (~15k tokens for IMPLEMENT context budget).
    """

    def split(self, index: list["FileIndex"], max_files_per_module: int = 10) -> list[dict]:
        # Build adjacency from includes/imports
        graph = {}
        for fi in index:
            deps = set()
            for inc in fi.includes:
                # Find which indexed file this include resolves to
                for other in index:
                    if inc in other.path or other.path.endswith(inc):
                        deps.add(other.path)
            graph[fi.path] = deps

        # Tarjan's SCC algorithm
        sccs = self._tarjan_scc(graph)

        # Group SCCs into modules
        modules = []
        current_module = {"files": [], "total_lines": 0}
        for scc in sccs:
            scc_lines = sum(
                fi.line_count for fi in index if fi.path in scc
            )
            if (len(current_module["files"]) + len(scc) > max_files_per_module
                    or current_module["total_lines"] + scc_lines > 5000):
                if current_module["files"]:
                    modules.append(current_module)
                current_module = {"files": list(scc), "total_lines": scc_lines}
            else:
                current_module["files"].extend(scc)
                current_module["total_lines"] += scc_lines

        if current_module["files"]:
            modules.append(current_module)

        # Name modules and compute dependencies
        for i, mod in enumerate(modules):
            mod["name"] = f"module_{i:02d}"
            mod["dependencies"] = self._compute_module_deps(mod, modules, graph)

        return modules
```

## Implementation Priority

### Phase 1: Immediate Impact (Weeks 1-3)

Focus: speed and extensibility — the changes users will feel immediately.

| Feature | Section | Effort | Impact | Dependencies |
|---------|---------|--------|--------|-------------|
| Parallel IMPLEMENT | 2A | Medium | 4x speed on IMPLEMENT stage | Plan must include dependency info |
| Smart Reflect | 2B | Low | 6x speed on REFLECT stage | Regex patterns from existing rules |
| Skill System | 3 | Medium | Enables all non-migration use cases | Refactor of template system |
| Analyze Cache | 2C | Low | Skip re-analysis on re-run | Hash-based keying |

**Phase 1 target: 460s -> ~150s, skill system operational.**

### Phase 2: Reliability (Weeks 4-6)

Focus: robustness for production use.

| Feature | Section | Effort | Impact | Dependencies |
|---------|---------|--------|--------|-------------|
| State Machine | 1 | High | Formal backtracking, auditable transitions | Core refactor of engine.py |
| Checkpointing | 7 | Medium | Resume after crash, saves ~200s on failure | State Machine |
| Adaptive Eval | 6 | Medium | Quality scales with source complexity | Analysis output format |
| Safety Guard | 9 | Low | Catch security issues before write | Independent |

**Phase 2 target: 150s -> ~120s, zero-loss crash recovery, adaptive quality.**

### Phase 3: Cutting Edge (Weeks 7-10)

Focus: advanced capabilities for complex projects.

| Feature | Section | Effort | Impact | Dependencies |
|---------|---------|--------|--------|-------------|
| Semantic Memory | 5 | Medium | Better context selection | Replaces truncation logic |
| Multi-File Pipeline | 4 | High | Project-level migration | Skill system, indexer |
| Clarification | 8 | Low | Handles ambiguous requirements | State Machine (pause/resume) |
| Long-Horizon Reliability | 10 | Medium | Prevents state corruption | State Machine, checkpointing |
| 20k+ Line Support | 11 | High | Enterprise-scale projects | Multi-file pipeline |

**Phase 3 target: multi-file projects, 20k+ lines, ambiguity handling.**

## Alternatives Considered

### 1. Agent Loop Instead of State Machine

**Rejected.** An open-ended agent loop (like Claude Code or Aider) lets the LLM decide "what to do next." This is catastrophic for weak models — they cannot reliably self-direct over long sequences. The v0.2 evidence confirms: fixed pipelines outperform agent loops for 20B models (Agentless research, `docs/research/references.md`).

The state machine preserves the fixed-pipeline advantage while adding backtracking — the LLM still never decides which state comes next, only the deterministic transition table does.

### 2. LLM-Based Context Scoring (Instead of Heuristic Importance)

**Rejected for v0.3.** Using the LLM to score context importance would produce better scores but costs an additional LLM call per prompt construction. At 49 calls per run, this adds ~50% overhead. The heuristic importance scoring (Section 5) achieves 80% of the quality at zero additional cost. LLM-based scoring can be added as an opt-in feature in v0.4 when speed is less constrained.

### 3. Full AST Parsing (Instead of Regex Indexing)

**Rejected for v0.3.** A proper Pro*C parser (using `pycparser` or custom grammar) would produce more accurate file indices than regex. However:
- Pro*C has no standard AST parser (it is C with embedded SQL, requiring both a C parser and SQL parser)
- Regex handles 90%+ of the structural extraction we need (function names, EXEC SQL, includes)
- AST parsing adds a dependency and maintenance burden
- Can be added in v0.4 for languages with good parser support (Java via `tree-sitter`)

### 4. Streaming LLM Calls (Instead of Batch)

**Considered.** Streaming responses would let us start parsing FILE: markers before the full response is complete, potentially saving time. However:
- v0.2 already uses non-streaming for repair (see `forge.py:1509-1516` — streaming is disabled when tools are present)
- Text-based protocol requires seeing the full FILE: block before writing
- Complexity of partial parsing outweighs the ~5-10% speed gain
- Revisit when the LLM response time (not total time) becomes the bottleneck

## Consequences

### Positive

- **3.8x speed improvement** (460s -> 120s target) makes iterative development practical
- **Multi-file support** unlocks real-world project migration (not just single-file demos)
- **Skill system** enables non-migration use cases (greenfield, refactor, test-gen, review) without code changes
- **State machine + checkpointing** eliminates wasted compute on crash/failure (resume from last checkpoint)
- **Adaptive eval** generates criteria that match source complexity (134 criteria for SETTLE_BAT.pc, 8 for simple SELECT)
- **Safety guard** catches security issues deterministically (no LLM cost, 100% detection rate for known patterns)
- **Backtracking with history** avoids repeating failed fixes (v0.2 retry loop has no memory of previous attempts)
- **Semantic memory** preserves high-value context while dropping low-value content (vs v0.2's indiscriminate truncation)

### Negative

- **Significant complexity increase.** v0.2 is ~500 lines of pipeline code. v0.3 will be ~3,000+. Mitigation: each component (state machine, skills, memory, safety) is independently testable.
- **Parallel execution adds debugging difficulty.** Race conditions in parallel IMPLEMENT are possible if two files write to the same path. Mitigation: plan validation ensures no path conflicts; semaphore limits concurrency.
- **Heuristic importance scoring may discard relevant context.** The 0.0-1.0 importance weights are tuned by hand. Mitigation: weights are configurable per skill; fall back to v0.2 truncation if memory manager produces worse results.
- **Skill system requires per-domain investment.** Each new skill (e.g., C-to-Rust migration) needs ~200 lines of prompts and criteria. Mitigation: base skill provides reasonable defaults; only the system prompt is truly mandatory.
- **Checkpoint files accumulate.** A 22-file migration produces ~25 checkpoint files (~50KB). Mitigation: auto-prune checkpoints older than 7 days; keep only latest per state.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Parallel IMPLEMENT introduces race conditions | Low | Medium | Dependency graph ensures independent files; semaphore limits concurrency to 3 |
| Smart Reflect's deterministic fixes miss edge cases | Medium | Low | LLM Tier 2 handles complex files; regex patterns are conservative |
| State machine adds latency via checkpointing | Low | Low | Checkpoint is JSON write (~1ms); negligible vs LLM call (~9s) |
| Adaptive eval generates too many/few criteria | Medium | Medium | Cap at 50; always include universal criteria (sequence, persistence) |
| Semantic memory discards critical context | Medium | High | Priority-based: system_prompt and fix_instruction always included (weight 1.0/0.95) |
| 20k+ line module splitting produces unbalanced modules | Medium | Low | Configurable max_files_per_module; manual override via `--module-config` |
| Clarification mode blocks CI/CD pipelines | Low | Medium | Batch mode auto-resolves; strict mode fails fast |

## Related

- ADR-001: `/Users/bonomoon/Workspace/redef/roominos/docs/adr/001-roominos-cli-architecture.md` — v0.2 architecture (this ADR extends)
- Forge proxy: `/Users/bonomoon/Workspace/redef/roominos/forge/forge.py` (1753 lines) — existing compensation strategies being superseded
- Context management: `forge.py:509-533` (budget check), `forge.py:594-644` (summarization), `forge.py:701-729` (truncation) — replaced by Semantic Memory
- Tool simplification: `forge.py:453-502` — no longer needed (text-based protocol)
- JSON repair: `forge.py:369-451` — no longer needed (text-based protocol)
- Text-to-tool extraction: `forge.py:1224-1326` — inspiration for v0.2 text protocol, now first-class
- Roo mode rules: `.roo/rules-coder/02-java-spring.md`, `.roo/rules-reviewer/02-migration-checks.md` — extracted into MigrationSkill
- Complex batch verification: `demos/migration/task_010_complex_batch/verification.md` (134 criteria) — target for Adaptive Eval to auto-generate
- Research references: `docs/research/references.md` — Agentless (fixed pipeline), ReWOO (plan-first), Alpha-UMi (role decomposition)
- Server optimization proposal: `docs/proposal-server-optimization.md` — Constrained Decoding (server-side complement to Roominos)
- Workflow guide: `docs/workflow-20b.md` — manual batch protocol that Roominos automates
