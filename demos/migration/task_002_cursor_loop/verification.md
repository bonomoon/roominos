# Verification: Task 002

## Acceptance Criteria

1. **Employee entity** with: id, name, salary (BigDecimal), deptId, status
2. **Repository query** filters by deptId and status='ACTIVE', ordered by name
3. **Service method** computes:
   - Total salary using BigDecimal (not double)
   - Employee count
   - Returns DTO with list + aggregates
4. **No N+1 problem** — single query fetches all needed data
5. **Memory safety** — for large departments, uses pagination or streaming (not loading all into memory)
6. **Test exists** verifying aggregation logic with known test data
