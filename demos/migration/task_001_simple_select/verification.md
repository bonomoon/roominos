# Verification: Task 001

## Acceptance Criteria

1. **Entity class exists** with fields: id (Long), name (String), email (String), balance (BigDecimal)
2. **Repository interface** extends JpaRepository with findById
3. **Service method** handles:
   - User found → returns UserDto with all fields
   - User not found → throws or returns Optional.empty()
   - NULL balance → BigDecimal is null, not 0
4. **Data type mapping**:
   - int user_id → Long id
   - char user_name[51] → String name (@Size(max=50))
   - char user_email[101] → String email (@Size(max=100))
   - double balance with indicator → BigDecimal balance (nullable)
5. **Test exists** that verifies all three scenarios (found, not found, null balance)
