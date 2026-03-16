# GPT-OSS-20B Workflow Guide

## Prerequisites
- VS Code + Roo Code extension (3.4+ or 3.51+)
- Forge proxy running (see Setup below)
- .roomodes and .roo/ copied to project root

## Forge Setup

### Windows
```cmd
# Extract forge-win-x64.zip
start.bat http://gpt-oss-server:8000/v1 9090 user@company.com
```

### Mac/Linux
```bash
./start.sh http://gpt-oss-server:8000/v1 9090 user@company.com
```

### Roo Code Settings
```
Provider:   OpenAI Compatible
Base URL:   http://localhost:9090/v1
API Key:    (your GPT-OSS API key)
Model ID:   openai/gpt-oss-20b
```

## The Golden Rule: Small Batches + Fresh Context

20B has limited context. Follow this protocol:
1. **1-2 files per conversation** — never more
2. **New Task (+) after every batch** — resets context
3. **No Orchestrator mode** — use Coder mode directly
4. **Skip update_todo_list** — just create files

## Workflow: Feature Development

### Phase 1: Plan (Planner mode)
```
Read [source file] and create a plan.md for [task description].
Break into batches of 1-2 files each.
```

### Phase 2: Implement (Coder mode, batch by batch)

#### Batch 1: Project setup
```
Create pom.xml for [project].
Spring Boot 3.2, JDK 17, Spring Data JPA, H2 for test.
```
→ New Task (+)

#### Batch 2: Entity
```
Create src/main/java/com/example/entity/[Name].java
@Entity with @SequenceGenerator, BigDecimal for money fields.
```
→ New Task (+)

#### Batch 3: Repository
```
Create src/main/java/com/example/repository/[Name]Repository.java
JpaRepository<[Entity], Long>
```
→ New Task (+)

#### Batch 4: Service
```
Create src/main/java/com/example/service/[Name]Service.java
@Service with @Transactional. Inject [Name]Repository.
Methods: findAll, findById, save, delete.
```
→ New Task (+)

#### Batch 5: Controller
```
Create src/main/java/com/example/controller/[Name]Controller.java
@RestController, @RequestMapping("/api/[name]").
CRUD endpoints using [Name]Service. Return ResponseEntity.
```
→ New Task (+)

#### Batch 6: DTO
```
Create src/main/java/com/example/dto/[Name]Request.java
and src/main/java/com/example/dto/[Name]Response.java
Use record types. Include validation annotations on Request.
```
→ New Task (+)

#### Batch 7: Config
```
Create src/main/resources/application.yml
Spring Boot datasource for H2 (test profile) and Oracle (prod profile).
JPA: show-sql=true, ddl-auto=validate.
```
→ New Task (+)

#### Batch 8: Tests
```
Create src/test/java/com/example/service/[Name]ServiceTest.java
JUnit 5 + Mockito. Test findAll, findById (found and not found), save, delete.
```
→ New Task (+)

### Phase 3: Verify (Runner mode)
```
Run mvn clean test and report results.
```

### Phase 4: Review (Reviewer mode)
```
Review the implementation against [verification.md / checklist].
Report CRITICAL, WARNING, INFO findings.
```

## Workflow: Pro*C to Java Migration

### Phase 1: Analyze (Planner mode)
```
Read [file].pc (lines 1-500) and list:
- All EXEC SQL statements
- All host variables
- Error handling patterns (WHENEVER, GOTO)
- Cursor declarations
```
→ New Task (+)
```
Read [file].pc (lines 500-1000) and continue the analysis.
```
→ Repeat until file fully analyzed

### Phase 2: Plan
```
Based on the analysis, create plan.md for migrating [file].pc to Java/Spring.
1-2 files per batch. Oracle DB, Spring Data JPA.
```

### Phase 3: Implement (same batch protocol as Feature Development above)

Typical migration batches:

#### Batch 1: Entity (from host variable structs)
```
Create src/main/java/com/example/entity/[Name].java
Mirror the Pro*C struct fields. Use @Column(name="ORACLE_COL") for exact column names.
BigDecimal for NUMBER fields, LocalDate for DATE fields.
```
→ New Task (+)

#### Batch 2: Repository (from EXEC SQL queries)
```
Create src/main/java/com/example/repository/[Name]Repository.java
JpaRepository<[Entity], Long>.
Add @Query methods for custom SQL from the Pro*C analysis:
  [paste the EXEC SQL SELECT statements here]
```
→ New Task (+)

#### Batch 3: Service (from Pro*C business logic)
```
Create src/main/java/com/example/service/[Name]Service.java
Migrate this Pro*C logic to Java:
  [paste the relevant C logic, max ~50 lines]
Use @Transactional for operations that had EXEC SQL COMMIT.
Replace WHENEVER SQLERROR with try/catch throwing custom exceptions.
```
→ New Task (+)

#### Batch 4: Exception handling (from WHENEVER / GOTO patterns)
```
Create src/main/java/com/example/exception/[Name]Exception.java
and src/main/java/com/example/exception/GlobalExceptionHandler.java
Map the original SQLCODE values to HTTP status codes.
```
→ New Task (+)

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "Model did not provide any response" | Context too large | New Task (+) to reset |
| "unknown tool update_todo_list" | 20B can't use this tool | Tell it: "todo list 쓰지 마" |
| "API Request Failed" | Forge not running or wrong port | Check Forge terminal |
| Tool name error | 20B outputs wrong name | Forge auto-aliases (if running) |
| Empty response loop | Model stuck | New Task (+) with simpler prompt |
| Response very slow | Context budget high | Check Forge logs for token count |

## Tips
- Shorter prompts = better results
- Korean prompts work, but English is slightly more reliable for code tasks
- If model loops on same error 3 times → New Task (+) with different approach
- Check Forge logs: `python analyze_logs.py ./logs/` for patterns
- If context > 20k tokens in Forge log → definitely New Task (+)

## Context Budget Reference
- 20B effective context: ~32k tokens
- Forge system prompt + tools: ~8k tokens
- Available for your code: ~24k tokens
- Safe per-batch budget: ~15k tokens (1-2 files)
