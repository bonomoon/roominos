# Demo: Java/Spring Application Building

## Purpose

Benchmark tasks for evaluating how well GPT-OSS + Roo Code handles building Java/Spring applications from scratch with Oracle database.

## Tasks

| Task | Difficulty | Focus Area | Tech Stack |
|------|-----------|-----------|------------|
| task_001 | Easy | CRUD REST API | Spring Data JPA + Oracle |
| task_002 | Medium | Dynamic search with QueryDSL | QueryDSL + JPA + Pagination |
| task_003 | Hard | Batch processing pipeline | Spring Batch + JDBC + Oracle procedures |

## Prerequisites

- JDK 17 or 21
- Maven 3.9+
- Oracle database (or Testcontainers with gvenzl/oracle-xe)
- Oracle JDBC driver (ojdbc11)

## How to Use

1. Give Roo Code (in Planner mode) the task description
2. Let it produce research.md and plan.md
3. Switch to Coder mode and execute the plan
4. Run the verification criteria to measure success
