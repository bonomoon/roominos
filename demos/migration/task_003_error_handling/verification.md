# Verification: Task 003

## Acceptance Criteria

1. **Account entity** with: id, balance (BigDecimal), lastUpdated (LocalDateTime)
2. **TransferLog entity** for audit trail
3. **Service method** transfer(fromId, toId, amount):
   - Pessimistic lock on source account (SELECT FOR UPDATE → @Lock)
   - Validates sufficient balance (throws InsufficientFundsException)
   - Debit + Credit + Log in single transaction
   - On ANY SQL error: rollback to savepoint (partial rollback)
   - Uses BigDecimal for all monetary calculations
4. **Exception hierarchy**:
   - InsufficientFundsException (business logic)
   - AccountNotFoundException (not found)
   - TransferFailedException (SQL error wrapper)
5. **Transaction behavior**:
   - Success: all 3 statements committed atomically
   - Insufficient funds: no DB changes
   - SQL error mid-transfer: rollback to savepoint, source balance unchanged
6. **Tests verify** all 3 scenarios with real DB (Testcontainers + Oracle)
