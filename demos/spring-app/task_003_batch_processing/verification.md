# Verification: Spring Task 003 - Batch Processing

## Acceptance Criteria

### Setup
- [ ] pom.xml includes spring-boot-starter-batch, ojdbc11
- [ ] Batch job configuration class with @EnableBatchProcessing
- [ ] Oracle schema for PROCESSED_TRANSACTIONS table

### Pipeline
- [ ] FlatFileItemReader configured for CSV with header skip
- [ ] ItemProcessor validates mandatory fields and enriches from Oracle
- [ ] JdbcBatchItemWriter uses batch insert (not individual inserts)
- [ ] Chunk size is configurable via application.yml

### Resilience
- [ ] Invalid records skipped (logged to skip table or log file)
- [ ] DB transient errors retried up to 3 times
- [ ] Job can restart from last failed chunk

### Oracle Integration
- [ ] Spring Batch metadata tables created in Oracle
- [ ] Post-processing stored procedure called after job completion
- [ ] JDBC batch operations use bind variables

### Tests
- [ ] Test: process valid CSV → all records in PROCESSED_TRANSACTIONS
- [ ] Test: CSV with invalid rows → valid processed, invalid skipped
- [ ] Test: job restart after failure resumes correctly
- [ ] All tests pass: mvn test
