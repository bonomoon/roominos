# Demo: C/Pro*C to Java/Spring Migration

## Purpose

Benchmark tasks for evaluating how well GPT-OSS + Roo Code handles migrating legacy C/Pro*C programs to modern Java/Spring applications with Oracle database.

## Tasks

| Task | Difficulty | Pro*C Constructs | Java Target |
|------|-----------|------------------|-------------|
| task_001 | Easy | Simple SELECT INTO | Spring Data JPA Repository |
| task_002 | Medium | Cursor DECLARE/OPEN/FETCH/CLOSE loop | JPA Stream or pagination |
| task_003 | Hard | WHENEVER SQLERROR + SAVEPOINT + multi-table | @Transactional + exception hierarchy |

## How to Use

1. Give Roo Code (in Planner mode) the task description and input.pc
2. Let it produce research.md and plan.md
3. Switch to Coder mode and execute the plan
4. Run the verification criteria to measure success

## Measurement

Each task has:
- `input.pc` — the Pro*C source to migrate
- `metadata.json` — difficulty, constructs, expected patterns
- `expected/` — description of expected Java output structure
- `verification.md` — acceptance criteria and test approach
