# Verification: Spring Task 001 - CRUD API

## Acceptance Criteria

### Structure
- [ ] pom.xml with Spring Boot 3, JPA, Oracle, Lombok, Testcontainers dependencies
- [ ] application.yml with Oracle datasource configuration
- [ ] Layered package structure: entity, repository, service, controller, dto, exception

### Entity
- [ ] Product entity with correct Oracle annotations
- [ ] Oracle sequence generator (not IDENTITY)
- [ ] BigDecimal for price (not Double)
- [ ] Audit fields with @PrePersist/@PreUpdate

### API
- [ ] All 5 REST endpoints return correct HTTP status codes
- [ ] Pagination works on list endpoint
- [ ] Input validation returns 400 with error details
- [ ] Not-found returns 404 with message

### Tests
- [ ] Repository test with Testcontainers + Oracle
- [ ] Service test (unit, mocked repository)
- [ ] Controller test (@WebMvcTest, mocked service)
- [ ] All tests pass: mvn test
