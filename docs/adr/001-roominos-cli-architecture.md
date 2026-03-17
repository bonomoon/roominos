# ADR-001: Roominos CLI Architecture

> **Status**: Proposed
> **Date**: 2026-03-17
> **Context**: Forge proxy reaches ceiling — weak models need a fundamentally different orchestration approach

## Context

### The Problem

We have proven that GPT-OSS-20B can produce correct code (98% success, 93% task score via Forge proxy). But the delivery mechanism — Roo Code with JSON tool calling — is the bottleneck, not the model itself.

**Evidence from benchmarks:**

| Approach | Success Rate | Cost per 12 files | Latency |
|----------|-------------|-------------------|---------|
| 20B direct API (text, no tools) | 98% (50/51) | $0.002 | ~3s/file |
| 20B + Forge + Roo Code (tool calling) | ~60% effective | ~$0.02 (retries) | ~15s/file |
| 20B raw Roo Code (no Forge) | 0% | N/A | hangs |

The core issue: **Roo Code requires JSON function calling, which weak models cannot reliably produce.** Forge compensates (JSON repair, tool name aliasing, text-to-tool extraction at `forge.py:1224-1326`), but this is fundamentally post-hoc symptom treatment. The model's raw text output is correct — it is the structured JSON wrapping that fails.

### What We Learned from Forge

Forge (`forge.py`, 1753 lines) implements 15+ compensation strategies:

1. JSON repair (`fix_trailing_commas`, `fix_missing_closing`, `fix_unescaped_quotes` at lines 369-451)
2. Tool name sanitization and aliasing (lines 985-1057)
3. Text-to-tool extraction / NonNativeToolCallingMixin pattern (lines 1224-1326)
4. Context budget management (lines 509-533, 701-729)
5. Conversation history summarization (lines 594-644)
6. Deferred tool schema loading (lines 655-694)
7. System prompt compression (lines 924-978)
8. Diff failure recovery with circuit breaker (lines 777-850)
9. Domain-specific guidance injection (lines 853-921)
10. Tool result size limiting (lines 540-587)

Despite all this, the fundamental architecture is wrong for weak models: we are forcing a text-native model through a JSON-structured pipe, then repairing the damage on the other side.

### What Works: Text-Based Interaction

Aider proved that text-based edit formats (SEARCH/REPLACE blocks) work well for weak models. OpenHands' `NonNativeToolCallingMixin` confirms that text-based tool calling is viable. Our own Forge `extract_tool_calls_from_text()` already does this — but reactively, after the model has already failed at JSON.

The insight: **if we design the interaction as text-first from the start, we eliminate the entire class of JSON structural failures.**

### Why Not Just Extend Forge

Forge is an HTTP proxy that patches Roo Code requests/responses. It cannot:
- Control the pipeline (which file to edit next, when to verify)
- Enforce context budget between stages (analyze vs. plan vs. implement)
- Run an AI-as-a-Judge verification step
- Chunk large files across multiple LLM calls
- Apply domain-specific templates (Pro*C migration vs. greenfield Spring app)

These require an orchestrator that owns the entire interaction loop, not a middleware that patches someone else's loop.

## Decision

### Build Roominos CLI: a text-based pipeline orchestrator for weak LLMs

Roominos CLI is a standalone command-line tool that orchestrates coding tasks through a fixed pipeline, using only text-based LLM interaction (no JSON function calling). It incorporates an AI-as-a-Judge verification step and manages context budgets per stage.

### Technical Moats (vs Existing Tools)

| Feature | OMC / Claude Code | Aider | OpenCode | Roominos CLI |
|---------|-------------------|-------|----------|--------------|
| Weak model support | No (requires Opus/Sonnet) | Partial (whole mode) | No (tool calling) | Yes (designed for 20B) |
| AI-as-a-Judge | No | No | No | Yes (built-in verify stage) |
| Per-stage context budget | No | Partial (repo map) | No | Yes (32k analyze, 15k implement) |
| Text-based tools | No (JSON tool calling) | Yes (SEARCH/REPLACE) | No (JSON tool calling) | Yes (FILE/RUN/READ markers) |
| Pipeline stages | No (single agent loop) | No (single loop) | No (single loop) | Yes (analyze, plan, implement, verify) |
| Domain templates | No | No | No | Yes (Pro\*C migration, Spring CRUD) |
| Forge proxy compat | N/A | N/A | N/A | Yes (optional, for Roo Code fallback) |
| Offline operation | No (cloud API) | Yes | Yes | Yes (local LLM only) |
| Verification retry loop | No | No (manual) | No | Yes (judge-driven, max 3 retries) |

### Architecture

```
roominos/
  cli/
    __init__.py
    main.py                  # CLI entry point (argparse)
    config.py                # Configuration management
    pipeline/
      __init__.py
      engine.py              # Pipeline orchestrator (stage sequencing)
      stages/
        __init__.py
        analyze.py           # Stage 1: source analysis
        plan.py              # Stage 2: implementation planning
        implement.py         # Stage 3: file generation (per-file)
        verify.py            # Stage 4: AI-as-a-Judge
    llm/
      __init__.py
      client.py              # Text-based LLM client (httpx, no tool calling)
      parser.py              # Parse FILE/RUN/READ markers from LLM output
      budget.py              # Context token budget tracking
    tools/
      __init__.py
      executor.py            # Execute parsed tool actions (write file, run cmd)
      file_ops.py            # File read/write/chunk operations
      runner.py              # Subprocess execution (mvn, gcc, etc.)
    judge/
      __init__.py
      judge.py               # AI-as-a-Judge: separate LLM call for validation
      criteria.py            # Acceptance criteria parser
      retry.py               # Retry logic based on judge feedback
    templates/
      __init__.py
      base.py                # Base template class
      migration.py           # Pro*C to Java/Spring migration template
      greenfield.py          # New Spring Boot app template
      crud.py                # CRUD API template
    context/
      __init__.py
      chunker.py             # Large file chunking (>200 lines)
      summarizer.py          # Inter-stage context summarization
      budget.py              # Token budget enforcement per stage
    artifacts/               # Stage output storage
      analysis.json          # Stage 1 output
      plan.json              # Stage 2 output
      generated/             # Stage 3 output (generated source files)
      judge_report.json      # Stage 4 output
  forge/                     # Existing Forge proxy (unchanged)
    forge.py
    ...
```

### Component Responsibilities

#### 1. CLI Entry Point (`cli/main.py`)

```python
"""
Roominos CLI: text-based pipeline orchestrator for weak LLMs.

Usage:
  roominos migrate --source SETTLE_BAT.pc --output java-migration/
  roominos create --template spring-crud --name ProductService --output product-api/
  roominos implement --plan plan.json --output src/
  roominos verify --files src/ --criteria verification.md
"""

import argparse
from roominos.pipeline.engine import PipelineEngine
from roominos.config import RoominosConfig

def main():
    parser = argparse.ArgumentParser(description="Roominos CLI")
    subparsers = parser.add_subparsers(dest="command")

    # roominos migrate
    migrate_p = subparsers.add_parser("migrate", help="Migrate legacy code")
    migrate_p.add_argument("--source", required=True, help="Source file(s) to migrate")
    migrate_p.add_argument("--output", required=True, help="Output directory")
    migrate_p.add_argument("--template", default="proc-to-java",
                           help="Migration template (default: proc-to-java)")
    migrate_p.add_argument("--criteria", help="Verification criteria file")

    # roominos create
    create_p = subparsers.add_parser("create", help="Create new project/feature")
    create_p.add_argument("--template", required=True,
                          help="Template: spring-crud, spring-batch, etc.")
    create_p.add_argument("--name", required=True, help="Primary entity/feature name")
    create_p.add_argument("--output", required=True, help="Output directory")

    # roominos verify
    verify_p = subparsers.add_parser("verify", help="Run AI-as-a-Judge on files")
    verify_p.add_argument("--files", required=True, help="Directory to verify")
    verify_p.add_argument("--criteria", required=True, help="Verification criteria file")

    # Global options
    for p in [migrate_p, create_p, verify_p]:
        p.add_argument("--api-url", default="http://localhost:11434/v1",
                        help="LLM API base URL")
        p.add_argument("--model", default="gpt-oss-20b",
                        help="Model identifier")
        p.add_argument("--max-retries", type=int, default=3,
                        help="Max verification retry attempts")
        p.add_argument("--context-budget", type=int, default=15000,
                        help="Token budget per implementation batch")
        p.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    config = RoominosConfig.from_args(args)
    engine = PipelineEngine(config)
    engine.run(args.command, args)
```

#### 2. Pipeline Engine (`pipeline/engine.py`)

Orchestrates the four stages with context isolation between each:

```python
class PipelineEngine:
    """
    Fixed pipeline: ANALYZE -> PLAN -> IMPLEMENT -> VERIFY
    Each stage gets fresh context (no conversation history leakage).
    Each stage produces a JSON artifact consumed by the next.
    """

    def __init__(self, config: RoominosConfig):
        self.config = config
        self.llm = TextLLMClient(config.api_url, config.model)
        self.artifact_dir = config.output / ".roominos"

    def run(self, command: str, args):
        template = self._load_template(command, args)

        # Stage 1: ANALYZE
        print("[1/4] Analyzing source...")
        analysis = AnalyzeStage(self.llm, self.config).run(
            source_files=self._read_sources(args),
            template=template,
        )
        self._save_artifact("analysis.json", analysis)

        # Stage 2: PLAN
        print("[2/4] Creating implementation plan...")
        plan = PlanStage(self.llm, self.config).run(
            analysis=analysis,
            template=template,
        )
        self._save_artifact("plan.json", plan)

        # Stage 3: IMPLEMENT (per file, with context reset between files)
        print(f"[3/4] Implementing {len(plan['files'])} files...")
        generated_files = []
        for i, file_spec in enumerate(plan["files"]):
            print(f"  [{i+1}/{len(plan['files'])}] {file_spec['path']}")
            result = ImplementStage(self.llm, self.config).run(
                file_spec=file_spec,
                analysis=analysis,
                plan=plan,
                template=template,
            )
            generated_files.append(result)

        # Stage 4: VERIFY (AI-as-a-Judge)
        print("[4/4] Verifying with AI Judge...")
        criteria = template.get_acceptance_criteria(args)
        verdict = VerifyStage(self.llm, self.config).run(
            generated_files=generated_files,
            criteria=criteria,
        )

        # Retry loop: fix failed criteria
        retry_count = 0
        while verdict.has_failures() and retry_count < self.config.max_retries:
            retry_count += 1
            print(f"  Retry {retry_count}/{self.config.max_retries}: "
                  f"fixing {len(verdict.failures)} failed criteria...")
            for failure in verdict.failures:
                fix_result = ImplementStage(self.llm, self.config).run_fix(
                    failure=failure,
                    generated_files=generated_files,
                )
                generated_files = self._apply_fix(generated_files, fix_result)

            verdict = VerifyStage(self.llm, self.config).run(
                generated_files=generated_files,
                criteria=criteria,
            )

        self._save_artifact("judge_report.json", verdict.to_dict())
        self._write_output_files(generated_files, args.output)
        self._print_summary(verdict, retry_count)
```

#### 3. Text-Based LLM Client (`llm/client.py`)

All LLM interaction is text-in, text-out. No JSON function calling. No tool schemas. No structured output mode.

```python
class TextLLMClient:
    """
    Text-only LLM client. Sends plain text prompts, receives plain text responses.
    No tool calling, no function schemas, no response_format.

    Uses the same OpenAI-compatible /v1/chat/completions endpoint but
    with messages only (no tools array).
    """

    def __init__(self, api_url: str, model: str, timeout: int = 120):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def complete(self, prompt: str, system: str = "",
                       max_tokens: int = 4096) -> str:
        """Send a text prompt, return text response. No JSON parsing."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,  # Low temperature for deterministic code gen
            # NO "tools" key
            # NO "response_format" key
            # NO "tool_choice" key
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.api_url}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()

        # Extract text content (handle reasoning field for 20B compat)
        for choice in body.get("choices", []):
            msg = choice.get("message", {})
            content = msg.get("content") or msg.get("reasoning") or ""
            if content:
                return content

        return ""

    async def complete_chunked(self, chunks: list[str], system: str = "",
                                max_tokens: int = 4096) -> list[str]:
        """Process multiple chunks independently (context isolation)."""
        results = []
        for chunk in chunks:
            result = await self.complete(chunk, system=system,
                                          max_tokens=max_tokens)
            results.append(result)
        return results
```

#### 4. Text Tool Parser (`llm/parser.py`)

Parses structured actions from plain text LLM output. This replaces JSON tool calling entirely.

```python
"""
Text-based tool protocol parser.

The model outputs plain text with embedded action markers.
This parser extracts those markers into structured actions.

Supported markers:
  FILE: <path>        — Create or overwrite a file (content follows in fenced block)
  EDIT: <path>        — Edit an existing file (SEARCH/REPLACE block follows)
  RUN: <command>      — Execute a shell command
  READ: <path>        — Request to read a file (resolved by orchestrator)
  DONE: <message>     — Signal task completion
"""

import re
from dataclasses import dataclass
from enum import Enum

class ActionType(Enum):
    FILE = "file"
    EDIT = "edit"
    RUN = "run"
    READ = "read"
    DONE = "done"

@dataclass
class ParsedAction:
    action: ActionType
    target: str         # file path or command
    content: str = ""   # file content or edit block
    line: int = 0       # line number in LLM output where action was found

def parse_actions(text: str) -> list[ParsedAction]:
    """
    Extract all action markers from LLM text output.

    Examples:
        FILE: src/main/java/com/example/Entity.java
        ```java
        package com.example;

        @Entity
        public class Product {
            @Id
            private Long id;
            private String name;
        }
        ```

        RUN: mvn clean compile

        READ: pom.xml

        EDIT: src/main/java/com/example/Entity.java
        <<<<<<< SEARCH
        private String name;
        =======
        private String name;
        private BigDecimal price;
        >>>>>>> REPLACE

        DONE: All files created successfully.
    """
    actions = []

    # Pattern: FILE: <path> followed by fenced code block
    file_pattern = re.compile(
        r'^FILE:\s*(.+?)\s*\n'
        r'```[\w]*\n'
        r'(.*?)'
        r'\n```',
        re.MULTILINE | re.DOTALL
    )
    for match in file_pattern.finditer(text):
        actions.append(ParsedAction(
            action=ActionType.FILE,
            target=match.group(1).strip(),
            content=match.group(2),
            line=text[:match.start()].count('\n') + 1,
        ))

    # Pattern: EDIT: <path> followed by SEARCH/REPLACE block
    edit_pattern = re.compile(
        r'^EDIT:\s*(.+?)\s*\n'
        r'<<<<<<< SEARCH\n'
        r'(.*?)'
        r'\n=======\n'
        r'(.*?)'
        r'\n>>>>>>> REPLACE',
        re.MULTILINE | re.DOTALL
    )
    for match in edit_pattern.finditer(text):
        actions.append(ParsedAction(
            action=ActionType.EDIT,
            target=match.group(1).strip(),
            content=f"<<<<<<< SEARCH\n{match.group(2)}\n=======\n{match.group(3)}\n>>>>>>> REPLACE",
            line=text[:match.start()].count('\n') + 1,
        ))

    # Pattern: RUN: <command>
    run_pattern = re.compile(r'^RUN:\s*(.+)$', re.MULTILINE)
    for match in run_pattern.finditer(text):
        actions.append(ParsedAction(
            action=ActionType.RUN,
            target=match.group(1).strip(),
            line=text[:match.start()].count('\n') + 1,
        ))

    # Pattern: READ: <path>
    read_pattern = re.compile(r'^READ:\s*(.+)$', re.MULTILINE)
    for match in read_pattern.finditer(text):
        actions.append(ParsedAction(
            action=ActionType.READ,
            target=match.group(1).strip(),
            line=text[:match.start()].count('\n') + 1,
        ))

    # Pattern: DONE: <message>
    done_pattern = re.compile(r'^DONE:\s*(.+)$', re.MULTILINE)
    for match in done_pattern.finditer(text):
        actions.append(ParsedAction(
            action=ActionType.DONE,
            target=match.group(1).strip(),
            line=text[:match.start()].count('\n') + 1,
        ))

    # Sort by position in text
    actions.sort(key=lambda a: a.line)
    return actions
```

#### 5. AI-as-a-Judge (`judge/judge.py`)

A separate LLM call that validates generated code against acceptance criteria. The judge is stateless — it sees only the generated files and the criteria, not the implementation conversation.

```python
class AIJudge:
    """
    AI-as-a-Judge: validates generated files against acceptance criteria.

    Uses a separate LLM call (can be same model or different) to score
    each criterion as PASS or FAIL. On FAIL, extracts a specific fix
    instruction that the implement stage can act on.

    The judge prompt is carefully designed to be evaluative, not generative.
    The model does not need to write code — only assess whether criteria are met.
    This is a much easier task for weak models (classification vs generation).
    """

    def __init__(self, llm: TextLLMClient):
        self.llm = llm

    async def evaluate(self, files: list[GeneratedFile],
                       criteria: list[Criterion]) -> JudgeVerdict:

        # Build the judge prompt
        prompt = self._build_prompt(files, criteria)

        # Judge uses a strict system prompt that constrains output format
        system = (
            "You are a code reviewer. For each criterion, respond with exactly:\n"
            "  PASS (confidence%) - brief reason\n"
            "  FAIL (confidence%) - what is wrong | fix: specific instruction\n\n"
            "Rules:\n"
            "- Check the ACTUAL file content, not assumptions\n"
            "- PASS only if the criterion is fully satisfied\n"
            "- FAIL must include a concrete fix instruction\n"
            "- confidence% reflects how certain you are (50-100)\n"
            "- Do not generate code. Only evaluate."
        )

        response = await self.llm.complete(prompt, system=system, max_tokens=2048)
        return self._parse_verdict(response, criteria)

    def _build_prompt(self, files: list[GeneratedFile],
                      criteria: list[Criterion]) -> str:
        prompt_parts = ["## Generated Files\n"]

        for f in files:
            # Include file content, chunked if large
            content = f.content
            if len(content.split('\n')) > 150:
                lines = content.split('\n')
                content = '\n'.join(lines[:75]) + \
                          f'\n\n... [{len(lines) - 100} lines omitted] ...\n\n' + \
                          '\n'.join(lines[-25:])
            prompt_parts.append(f"### {f.path}\n```\n{content}\n```\n")

        prompt_parts.append("\n## Acceptance Criteria\n")
        for i, c in enumerate(criteria, 1):
            prompt_parts.append(f"{i}. {c.description}")

        prompt_parts.append(
            "\n\n## Your Evaluation\n"
            "For each numbered criterion above, write one line:\n"
            "  N. PASS (XX%) - reason\n"
            "  N. FAIL (XX%) - problem | fix: instruction\n"
        )

        return '\n'.join(prompt_parts)

    def _parse_verdict(self, response: str,
                       criteria: list[Criterion]) -> JudgeVerdict:
        """
        Parse judge response into structured verdict.

        Expected format per line:
          1. PASS (95%) - Entity uses @SequenceGenerator correctly
          2. FAIL (90%) - BigDecimal not used for balance | fix: Change Double to BigDecimal in Entity.java line 15
          3. PASS (85%) - Test covers found/not-found/null scenarios
        """
        results = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Match: N. PASS/FAIL (XX%) - reason [| fix: instruction]
            match = re.match(
                r'(\d+)\.\s*(PASS|FAIL)\s*\((\d+)%\)\s*[-:]\s*(.*)',
                line
            )
            if match:
                idx = int(match.group(1)) - 1
                passed = match.group(2) == "PASS"
                confidence = int(match.group(3))
                detail = match.group(4)

                fix_instruction = ""
                if not passed and "|" in detail:
                    parts = detail.split("|", 1)
                    detail = parts[0].strip()
                    fix_part = parts[1].strip()
                    if fix_part.lower().startswith("fix:"):
                        fix_instruction = fix_part[4:].strip()

                if 0 <= idx < len(criteria):
                    results.append(CriterionResult(
                        criterion=criteria[idx],
                        passed=passed,
                        confidence=confidence,
                        reason=detail,
                        fix_instruction=fix_instruction,
                    ))

        return JudgeVerdict(results=results)
```

### Data Flow

```
User: roominos migrate --source SETTLE_BAT.pc --output java-migration/

 STAGE 1: ANALYZE
  Input:  Source file (chunked if >200 lines)
  Prompt: "List all functions, EXEC SQL statements, host variables,
           error handling patterns, and business rules in this code."
  Output: analysis.json
  Budget: 32,000 tokens (source may span multiple LLM calls)
  Context: FRESH (no prior conversation)

 STAGE 2: PLAN
  Input:  analysis.json (NOT the source file — summary only)
  Prompt: "Create an implementation plan. 1 file per batch.
           Order: Entity -> Repository -> Service -> Controller -> DTO -> Config -> Test.
           For each file: path, dependencies, key requirements."
  Output: plan.json (ordered list of {path, type, requirements, dependencies})
  Budget: 15,000 tokens
  Context: FRESH (only analysis.json)

 STAGE 3: IMPLEMENT (repeated per file in plan)
  Input:  plan.json entry + relevant source chunks from analysis
  Prompt: "Create [path] with these requirements: [requirements].
           Reference source: [relevant Pro*C excerpt].
           Use these conventions: [template rules].
           Output the file using FILE: marker."
  Output: Generated source file (extracted via FILE: marker)
  Budget: 15,000 tokens per file
  Context: FRESH per file (no cross-file conversation leakage)

 STAGE 4: VERIFY (AI-as-a-Judge)
  Input:  All generated files + acceptance criteria
  Prompt: "Score each criterion PASS/FAIL with confidence%.
           FAIL must include a specific fix instruction."
  Output: judge_report.json
  Budget: 32,000 tokens
  Context: FRESH (only generated files + criteria)

 RETRY LOOP (max 3 attempts):
  If any FAIL with fix instruction:
    -> Re-run IMPLEMENT for the specific file with fix instruction appended
    -> Re-run VERIFY
  After 3 failures on same criterion:
    -> Report as unresolvable, suggest human review
```

### Text-Based Tool Protocol

The model never produces JSON tool calls. Instead, it outputs plain text with embedded action markers. The CLI parser (`llm/parser.py`) extracts these into structured actions.

#### FILE: Create or overwrite a file

```
FILE: src/main/java/com/example/entity/Product.java
```java
package com.example.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "TB_PRODUCT_MST")
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "productSeq")
    @SequenceGenerator(name = "productSeq", sequenceName = "SEQ_PRODUCT", allocationSize = 1)
    private Long id;

    @Column(name = "PRODUCT_NM", length = 100, nullable = false)
    private String name;

    @Column(name = "PRICE", precision = 18, scale = 2)
    private BigDecimal price;
}
```
```

#### EDIT: Modify part of an existing file

```
EDIT: src/main/java/com/example/entity/Product.java
<<<<<<< SEARCH
    private BigDecimal price;
}
=======
    private BigDecimal price;

    @Column(name = "CREATED_DT")
    private LocalDateTime createdAt;

    @PrePersist
    void onCreate() { this.createdAt = LocalDateTime.now(); }
}
>>>>>>> REPLACE
```

#### RUN: Execute a command

```
RUN: mvn clean compile -q
```

The CLI captures stdout/stderr and can feed results back to the model if the command fails.

#### READ: Request file content

```
READ: pom.xml
```

The CLI reads the file and includes its content in the next prompt. If the file exceeds 200 lines, it is automatically chunked.

#### DONE: Signal completion

```
DONE: Entity class created with @SequenceGenerator, BigDecimal for price, and audit fields.
```

### AI-as-a-Judge Protocol

#### Judge Prompt Template

```
You are reviewing generated Java/Spring code for a Pro*C migration.

## Generated Files

### src/main/java/com/example/entity/Product.java
```java
[full file content, chunked if >150 lines]
```

### src/main/java/com/example/repository/ProductRepository.java
```java
[full file content]
```

## Acceptance Criteria

1. Entity uses @SequenceGenerator (not GenerationType.IDENTITY)
2. All NUMBER(18,2) columns mapped to BigDecimal (not Double/double)
3. NULL indicator variables mapped to nullable types with explicit null handling
4. All EXEC SQL SELECT mapped to JPA @Query or repository method
5. @Transactional boundaries match COMMIT WORK locations in Pro*C
6. Test exists and covers found, not-found, and null scenarios

## Your Evaluation

For each numbered criterion above, write one line:
  N. PASS (XX%) - reason
  N. FAIL (XX%) - problem | fix: instruction
```

#### Judge Response (parsed by `judge.py`)

```
1. PASS (95%) - Entity uses @SequenceGenerator with sequenceName="SEQ_PRODUCT"
2. FAIL (90%) - balance field uses Double instead of BigDecimal | fix: Change line 23 in Product.java from 'private Double balance' to 'private BigDecimal balance'
3. PASS (85%) - Optional<Product> return type handles null correctly
4. PASS (90%) - findByAccountNo maps to EXEC SQL SELECT at source line 42
5. FAIL (80%) - Service wraps entire method in single @Transactional but Pro*C has mid-function COMMIT | fix: Split processSettlement() into two methods with separate @Transactional boundaries
6. PASS (92%) - ProductServiceTest covers all three scenarios with @SpringBootTest
```

#### Retry Flow

When the judge returns FAILs:

```python
# judge_report.json excerpt
{
  "failures": [
    {
      "criterion": "All NUMBER(18,2) columns mapped to BigDecimal",
      "confidence": 90,
      "reason": "balance field uses Double instead of BigDecimal",
      "fix_instruction": "Change line 23 in Product.java from 'private Double balance' to 'private BigDecimal balance'",
      "target_file": "src/main/java/com/example/entity/Product.java"
    }
  ]
}

# The implement stage receives the fix instruction as additional context:
# Prompt: "Fix this file. The judge found: [fix_instruction]. Apply the fix using EDIT: marker."
```

### Context Budget Management

Each pipeline stage operates within a strict token budget. This prevents the "dumb zone" degradation observed at 40% context usage (per Dex Horthy's research, already codified in Forge at `forge.py:514-519`).

| Stage | Budget | Rationale |
|-------|--------|-----------|
| ANALYZE | 32,000 tokens | Large source files need room; may span multiple calls |
| PLAN | 15,000 tokens | Input is analysis summary, not raw source |
| IMPLEMENT (per file) | 15,000 tokens | 1 file at a time; fresh context each file |
| VERIFY | 32,000 tokens | Must see all generated files + criteria |
| FIX (retry) | 8,000 tokens | Single file + specific fix instruction |

For source files exceeding the budget:

```python
class FileChunker:
    """
    Split large files into chunks that fit within token budget.
    Each chunk overlaps by 20 lines for context continuity.

    Strategy:
    - Files <= 200 lines: single chunk
    - Files > 200 lines: split at function boundaries (detect by indentation)
    - Each chunk prefixed with: "This is chunk N/M of [filename], lines X-Y"
    - Analysis results from all chunks are merged
    """

    def chunk(self, content: str, max_lines: int = 200, overlap: int = 20) -> list[str]:
        lines = content.split('\n')
        if len(lines) <= max_lines:
            return [content]

        chunks = []
        start = 0
        while start < len(lines):
            end = min(start + max_lines, len(lines))

            # Try to split at a function boundary (line starting with no indentation)
            if end < len(lines):
                for i in range(end, max(start + max_lines // 2, start), -1):
                    if lines[i].strip() and not lines[i][0].isspace() and lines[i][0] != '*':
                        end = i
                        break

            chunk_lines = lines[start:end]
            header = f"[Chunk {len(chunks)+1}, lines {start+1}-{end} of {len(lines)}]"
            chunks.append(header + '\n' + '\n'.join(chunk_lines))
            start = end - overlap  # Overlap for context continuity

        return chunks
```

### Template System

Templates encode domain-specific knowledge that weak models lack. Instead of hoping the model knows Spring conventions, we inject them.

```python
class MigrationTemplate(BaseTemplate):
    """
    Pro*C to Java/Spring migration template.

    Encodes the domain rules from:
    - .roo/rules-coder/02-java-spring.md (Oracle-specific rules)
    - .roo/rules-reviewer/02-migration-checks.md (equivalence checks)
    - demos/migration/task_*/verification.md (acceptance criteria patterns)
    """

    name = "proc-to-java"

    # System prompt injected into every LLM call during this template
    system_prompt = """You are migrating Pro*C (C with Embedded SQL) to Java/Spring Boot 3.

MANDATORY RULES:
- jakarta.persistence (NOT javax.persistence) for Spring Boot 3.x
- @SequenceGenerator for Oracle (NEVER GenerationType.IDENTITY)
- BigDecimal for ALL monetary/numeric fields (NEVER Double/double)
- @Transactional boundaries must match EXEC SQL COMMIT locations
- WHENEVER SQLERROR -> try/catch with specific exception types
- Indicator variables (ind == -1) -> nullable fields with explicit null check
- VARCHAR2(n) -> String with @Size(max=n)
- NUMBER(p,s) -> BigDecimal(precision=p, scale=s)
- DATE -> LocalDateTime (Oracle DATE includes time component)
- Use H2 for tests (application-test.yml), Oracle for production

OUTPUT FORMAT:
- Use FILE: marker to create files
- Use EDIT: marker to modify files
- Use RUN: marker to execute commands
- One file per response unless instructed otherwise"""

    # Acceptance criteria generated from source analysis
    def get_acceptance_criteria(self, args) -> list[Criterion]:
        return [
            Criterion("Entity uses @SequenceGenerator (not IDENTITY)"),
            Criterion("All NUMBER(18,2) columns use BigDecimal"),
            Criterion("All EXEC SQL SELECT mapped to JPA method or @Query"),
            Criterion("@Transactional boundaries match COMMIT WORK locations"),
            Criterion("WHENEVER SQLERROR mapped to try/catch"),
            Criterion("Indicator variables mapped to nullable types"),
            Criterion("Test class exists with found/not-found/null scenarios"),
            Criterion("application-test.yml exists with H2 config"),
        ]

    # Analysis prompt tailored for Pro*C
    def get_analyze_prompt(self, source_chunk: str) -> str:
        return f"""Analyze this Pro*C source code. List:

1. FUNCTIONS: name, line range, purpose
2. EXEC SQL: every SQL statement with type (SELECT/INSERT/UPDATE/DELETE/CURSOR)
3. HOST VARIABLES: name, C type, usage
4. INDICATOR VARIABLES: which host vars have indicators (NULL handling)
5. ERROR HANDLING: WHENEVER, GOTO labels, sqlca.sqlcode checks
6. TRANSACTION CONTROL: COMMIT, ROLLBACK, SAVEPOINT
7. BUSINESS RULES: any calculation logic, branching, special cases

Source:
```c
{source_chunk}
```"""

    # Plan prompt that enforces batch-size rules
    def get_plan_prompt(self, analysis: dict) -> str:
        return f"""Create an implementation plan for migrating this Pro*C to Java/Spring.

Analysis summary:
{json.dumps(analysis, indent=2)}

RULES:
- ONE file per batch (weak model constraint)
- Order: pom.xml -> Entity -> Repository -> Service -> Controller -> DTO -> Config -> Tests
- Each Entity must map ALL host variables from the analysis
- Each Repository must map ALL EXEC SQL from the analysis
- Service must preserve ALL transaction boundaries
- Tests in SEPARATE batches from implementation

Output a JSON array:
[
  {{"path": "pom.xml", "type": "config", "requirements": "Spring Boot 3.2, JPA, Oracle, H2 test, Lombok"}},
  {{"path": "src/main/.../Entity.java", "type": "entity", "requirements": "Map these host vars: ...", "source_refs": ["line 10-16"]}},
  ...
]"""
```

### Forge Integration (Optional Proxy Mode)

Roominos CLI can optionally route LLM calls through Forge proxy, reusing its JSON repair and SSE capabilities. This enables a hybrid mode where Roominos orchestrates the pipeline but Roo Code handles individual file edits.

```python
class TextLLMClient:
    def __init__(self, api_url: str, model: str, use_forge: bool = False,
                 forge_url: str = "http://localhost:9090/v1"):
        if use_forge:
            # Route through Forge for JSON repair + logging benefits
            self.api_url = forge_url
        else:
            # Direct to LLM API (text-only, no JSON repair needed)
            self.api_url = api_url
```

When Forge is enabled, Roominos benefits from:
- Request/response logging (.json + .md + SESSION_SUMMARY.md)
- Reasoning-to-content normalization (20B compatibility)
- Context budget warnings (independent check)

When Forge is disabled (default), Roominos operates fully standalone with zero dependencies beyond `httpx`.

## Alternatives Considered

### 1. Extend Forge Proxy Further

**Rejected.** Forge is fundamentally a request/response middleware. It cannot control pipeline sequencing, enforce per-stage context budgets, or run verification. Adding these capabilities would turn Forge into a full orchestrator pretending to be a proxy — wrong abstraction layer.

Forge remains valuable as: (a) a Roo Code compatibility layer, (b) a logging/debugging tool, and (c) an optional backend for Roominos when Roo Code integration is needed.

### 2. Use Aider Directly

**Rejected.** Aider has the right text-based approach (SEARCH/REPLACE, whole mode), but lacks:
- AI-as-a-Judge verification loop
- Per-stage context isolation (single conversation model)
- Domain-specific templates (Pro*C migration rules)
- Pipeline stages (analyze/plan/implement/verify as separate phases)
- Configurable context budgets per stage

Aider's edit format is a direct inspiration for Roominos' EDIT: marker. The SEARCH/REPLACE syntax is proven to work with weak models.

### 3. Build a VS Code Extension

**Rejected.** The problem is not the IDE interface — it is the LLM interaction model. A VS Code extension would still need to solve JSON tool calling (the hard problem). CLI is simpler to build, test, and distribute. IDE integration can be added later as a thin wrapper around the CLI.

### 4. Use OpenHands / SWE-agent

**Rejected for primary use, but architecturally informative.** OpenHands' `NonNativeToolCallingMixin` (already partially implemented in Forge at `forge.py:1224-1326`) confirms that text-based tool extraction works. SWE-agent's Agent-Computer Interface (custom shell commands) is conceptually similar to Roominos' action markers.

However, both are designed for capable models (Claude, GPT-4) with weak-model support as an afterthought. Roominos is designed weak-model-first.

### 5. Use Agentless (Fixed Pipeline, No Agent Loop)

**Most similar architecture.** Agentless uses a fixed Localize -> Repair -> Validate pipeline, which maps closely to Roominos' Analyze -> Plan -> Implement -> Verify. The key difference: Agentless targets bug fixing (single-file patches), while Roominos targets project generation (multi-file creation).

Roominos adopts Agentless' core insight that **fixed pipelines outperform open-ended agent loops for weak models** — the model does not need to decide "what to do next" because the pipeline dictates it.

## Consequences

### Positive

- **Weak models become productive.** The 20B model produces correct code 98% of the time via direct text — Roominos harnesses this without JSON overhead.
- **Pipeline is auditable.** Every stage produces a JSON artifact (`analysis.json`, `plan.json`, `judge_report.json`). Failures are traceable to a specific stage.
- **AI-as-a-Judge prevents quality degradation.** The verification step catches the remaining ~7% of errors before files are written. Classification (PASS/FAIL) is easier for weak models than generation.
- **Context isolation eliminates the "dumb zone."** Each stage starts fresh. No accumulated context degrades model performance. This directly addresses Dex Horthy's 40%-threshold finding.
- **Templates encode domain expertise.** The Pro*C migration rules from `.roo/rules-coder/02-java-spring.md` and `.roo/rules-reviewer/02-migration-checks.md` are baked into templates. The model does not need to know Spring conventions — the template tells it.
- **Offline-capable.** Only dependency is an OpenAI-compatible API endpoint. Works with local vLLM/ollama/llama.cpp.
- **Cost-effective.** No retries from JSON failures means fewer API calls. Text-only requests skip tool schema tokens (~2-8k per request). Estimated $0.002 per 12-file project vs $0.02 with Forge+Roo Code.

### Negative

- **New tool to maintain.** Roominos CLI is a separate codebase alongside Forge. However, the two share no code — CLI is Python with `httpx`, Forge is Python with `fastapi` — so maintenance burden is additive, not multiplicative.
- **Text parsing is heuristic.** The FILE:/EDIT:/RUN: protocol depends on the model following formatting instructions. Unlike JSON Schema enforcement (Constrained Decoding), there is no grammar-level guarantee. Mitigation: the markers are simple (one keyword + colon) and 20B follows them reliably in testing.
- **No IDE integration.** Users run the CLI in a terminal, not inside VS Code. Mitigation: output files are written to disk and appear in any editor. A VS Code task can wrap the CLI command.
- **Fixed pipeline is inflexible.** The 4-stage sequence is hardcoded. Some tasks (e.g., "add a single field to an entity") do not need analyze+plan stages. Mitigation: the CLI supports `roominos verify` as a standalone command, and `roominos implement --plan plan.json` to skip analysis. Individual stages can be run independently.
- **Judge quality depends on model capability.** If the 20B model cannot reliably evaluate criteria, the judge becomes a rubber stamp. Mitigation: judge prompts are evaluative (PASS/FAIL classification), not generative — a fundamentally easier task. Additionally, the judge model can be configured separately (e.g., use 120B for judging while 20B implements).

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Model ignores FILE: markers, outputs free-form text | Low (20B follows formatting well in testing) | Medium (file not created) | Fallback: treat entire response as file content if no markers found |
| Judge always passes (rubber stamp) | Medium (weak model may be lenient) | High (quality degradation) | Use stricter judge prompts; optionally route judge to stronger model |
| Template system becomes maintenance burden | Medium (each domain needs a template) | Low (templates are ~100 lines of prompts) | Start with 2 templates (migration, CRUD); add more based on demand |
| Context budget too restrictive for large files | Low (chunking handles most cases) | Medium (incomplete analysis) | Adjustable via `--context-budget` flag; chunker overlap ensures continuity |
| Text-based protocol conflicts with code content containing markers | Very low (FILE: at line start in generated Java is unlikely) | Low (false parse) | Markers require line-start position + specific syntax (colon + space + path) |

## Related

- Forge proxy: `/Users/bonomoon/Workspace/redef/roominos/forge/forge.py` (existing, 1753 lines)
- Workflow guide: `/Users/bonomoon/Workspace/redef/roominos/docs/workflow-20b.md` (manual batch protocol)
- Verification templates: `/Users/bonomoon/Workspace/redef/roominos/demos/migration/task_010_complex_batch/verification.md` (134 criteria)
- Research: `/Users/bonomoon/Workspace/redef/roominos/docs/research/references.md` (Agentless, ReWOO, Alpha-UMi, SWE-agent)
- Server proposal: `/Users/bonomoon/Workspace/redef/roominos/docs/proposal-server-optimization.md` (Constrained Decoding recommendation)
- AGENTS.md: `/Users/bonomoon/Workspace/redef/roominos/AGENTS.md` (Phase 3 roadmap: Plan-then-Execute, Adaptive edit format)
