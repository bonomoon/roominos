# Pro*C to Java/Spring Migration Review Checklist

## Purpose

When reviewing code that migrates C/Pro*C programs to Java/Spring, verify equivalence at every layer.

## SQL Statement Equivalence

### EXEC SQL SELECT → JPA/JDBC
| Pro*C | Java Equivalent | Check |
|-------|----------------|-------|
| EXEC SQL SELECT ... INTO :host_var | repository.findBy*() or jdbcTemplate.queryForObject() | Result mapping matches |
| EXEC SQL SELECT ... WHERE col = :var | @Query with @Param or method naming | Bind variable used (no concatenation) |
| Multi-table JOIN | @EntityGraph or JPQL JOIN FETCH | N+1 not introduced |

### EXEC SQL INSERT/UPDATE/DELETE → JPA/JDBC
| Pro*C | Java Equivalent | Check |
|-------|----------------|-------|
| EXEC SQL INSERT INTO ... VALUES (:vars) | repository.save(entity) or jdbcTemplate.update() | All columns mapped |
| EXEC SQL UPDATE ... SET ... WHERE | entity setter + save, or @Modifying @Query | WHERE clause preserved exactly |
| EXEC SQL DELETE FROM ... WHERE | repository.delete() or @Modifying @Query | Cascade behavior considered |

### Cursor Operations → Java Iteration
| Pro*C | Java Equivalent | Check |
|-------|----------------|-------|
| DECLARE cursor_name CURSOR FOR | @Query returning List<T> or Stream<T> | Memory for large results |
| OPEN cursor_name | (implicit in Spring) | N/A |
| FETCH cursor_name INTO :vars | Stream processing or pagination | Row-by-row preserved if needed |
| CLOSE cursor_name | (implicit, or try-with-resources for Stream) | Resource leak check |

## Data Type Fidelity

### CRITICAL: Precision Must Match

| Pro*C Type | Java Type | Verification |
|-----------|-----------|-------------|
| COMP-3 / PIC S9(n)V9(m) | BigDecimal(precision, scale) | Scale matches exactly |
| VARCHAR2(n) host variable | String | Max length preserved via @Size(max=n) |
| NUMBER(p,0) | Long or Integer | No precision loss |
| DATE host variable | LocalDateTime | Time component preserved |
| Indicator variable = -1 (NULL) | null / Optional | NULL semantics identical |

### Test Criterion
```
For every numeric computation in Pro*C:
  Java BigDecimal result must equal Pro*C result to exact decimal places
  Rounding mode must match (HALF_UP is most common in financial)
```

## Transaction Boundary Verification

| Pro*C | Java | Check |
|-------|------|-------|
| EXEC SQL COMMIT WORK | @Transactional (method-level commit) | Commit scope matches |
| EXEC SQL ROLLBACK WORK | Exception → automatic rollback | Rollback triggers match |
| EXEC SQL SAVEPOINT name | savepoint via TransactionTemplate | Partial rollback preserved |
| No explicit COMMIT (auto) | @Transactional propagation | Implicit commit behavior matches |
| EXEC SQL SET TRANSACTION READ ONLY | @Transactional(readOnly = true) | Read-only optimization |

### CRITICAL Check
```
Every EXEC SQL COMMIT in Pro*C must map to a @Transactional boundary in Java.
If Pro*C commits mid-function, Java must NOT wrap entire method in single transaction.
```

## Error Handling Parity

| Pro*C | Java | Check |
|-------|------|-------|
| WHENEVER SQLERROR GOTO error_handler | try/catch DataAccessException | All SQL errors caught |
| WHENEVER NOT FOUND GOTO not_found | EmptyResultDataAccessException or Optional.empty() | Empty result handled |
| WHENEVER SQLERROR CONTINUE | (no-op, but log) | Error silencing documented |
| sqlca.sqlcode | Specific exception types | Error codes mapped correctly |
| sqlca.sqlerrm | exception.getMessage() | Error messages preserved |

## Review Output Format for Migration

```
## Migration Review: [filename]

### SQL Equivalence
- [x] All SELECT statements mapped correctly
- [ ] **[C1] EXEC SQL at line 42**: Missing WHERE clause in Java equivalent — `Service.java:87`

### Data Type Fidelity
- [x] All numeric types use BigDecimal with correct scale
- [ ] **[W1] VARCHAR2(20) at line 15**: Java String has no @Size constraint — `Entity.java:23`

### Transaction Boundaries
- [x] COMMIT WORK maps to @Transactional correctly

### Error Handling
- [ ] **[C2] WHENEVER SQLERROR at line 5**: No equivalent try/catch in Java — `Service.java:45`

### Overall Assessment
Migration fidelity: [HIGH/MEDIUM/LOW]
Confidence: [percentage based on checks passed]
```

## Rules

- Every EXEC SQL statement in Pro*C must have a verified Java equivalent
- Every host variable must have a type-safe Java mapping
- Every error handler must have an exception handling equivalent
- If you cannot verify equivalence for any construct, flag it as CRITICAL
