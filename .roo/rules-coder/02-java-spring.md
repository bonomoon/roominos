# Java / Spring Development Rules

## CRITICAL: Common Mistakes to Avoid

- **NEVER use `org.hibernate.dialect.Oracle12cDialect`** — removed in Hibernate 6 (Spring Boot 3.x). Let Hibernate auto-detect the dialect, or omit the `dialect` property entirely.
- **NEVER use `GenerationType.IDENTITY` with Oracle** — Oracle does not support IDENTITY columns. Always use `GenerationType.SEQUENCE` + `@SequenceGenerator`.
- **NEVER use `javax.persistence`** with Spring Boot 3.x — use `jakarta.persistence` instead (Jakarta EE migration).
- **Always create `application-test.yml`** (or `application-test.properties`) with H2 datasource for tests. Tests must not depend on Oracle being available.
- **Always include a null/edge case test** when the Pro*C source uses indicator variables (e.g., `balance_ind == -1` → test that null balance is handled).

## Architecture Layers

Follow strict layered architecture. Each layer has specific responsibilities:

### Entity (@Entity)
- Annotate with @Entity and @Data (Lombok)
- ID: @Id + @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "SEQ_NAME")
- Oracle sequence: @SequenceGenerator(name = "SEQ_NAME", sequenceName = "ORACLE_SEQ", allocationSize = 1)
- FetchType.LAZY for all relationships (unless explicitly asked otherwise)
- Validation annotations: @NotNull, @Size, @Column(precision, scale) for NUMBER types
- Use @EntityGraph(attributePaths = {...}) on repository methods to avoid N+1

### Repository (@Repository)
- Interface extending JpaRepository<Entity, IdType>
- Use JPQL for @Query methods (not native SQL, unless Oracle-specific features needed)
- Use @EntityGraph for relationship queries
- Use DTO projections for multi-join queries
- Custom queries: prefer Spring Data method naming when possible

### Service (@Service)
- Interface + Impl pattern: UserService (interface) + UserServiceImpl (@Service)
- All dependencies via constructor injection (not @Autowired field injection)
- Return DTOs, not entities (unless internal service-to-service call)
- Use @Transactional for multiple DB operations
- Use .orElseThrow(() -> new EntityNotFoundException(...)) for lookups

### Controller (@RestController)
- @RequestMapping("/api/v1/resource") at class level
- Use @GetMapping, @PostMapping, @PutMapping, @DeleteMapping
- Resource-based paths: /users/{id} (no verbs like /getUser)
- Return ResponseEntity<ApiResponse<T>>
- All logic delegated to Service — controllers do mapping only

### DTO
- Use Java record (JDK 17+) or @Data class (JDK 8)
- Validation in constructor or via @Valid
- Separate Request and Response DTOs when shapes differ

## Oracle-Specific Rules

### Data Types
| Oracle | Java | Notes |
|--------|------|-------|
| NUMBER(p,s) | BigDecimal | Always BigDecimal for money/precision |
| NUMBER(n,0) where n<=9 | Integer | Safe for small integers |
| NUMBER(n,0) where n<=18 | Long | Safe for large integers |
| VARCHAR2(n) | String | Check for CHAR padding if migrating |
| DATE | LocalDateTime | Oracle DATE includes time component |
| TIMESTAMP | LocalDateTime | |
| CLOB | String or @Lob | Use @Lob for large text |
| BLOB | byte[] or @Lob | |

### Sequences
```java
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "mySeqGen")
@SequenceGenerator(name = "mySeqGen", sequenceName = "MY_TABLE_SEQ", allocationSize = 1)
private Long id;
```

### Pagination
```java
// Repository
Page<Entity> findByStatus(String status, Pageable pageable);

// Service
Pageable pageable = PageRequest.of(page, size, Sort.by("createdAt").descending());
```

## QueryDSL Rules

### Setup
- Use querydsl-jpa and querydsl-apt with Maven APT plugin
- Q-classes generated in target/generated-sources/

### Usage Patterns
```java
// Dynamic query building
BooleanBuilder builder = new BooleanBuilder();
if (name != null) builder.and(qUser.name.contains(name));
if (status != null) builder.and(qUser.status.eq(status));
return queryFactory.selectFrom(qUser).where(builder).fetch();
```

### Projection
```java
// DTO projection with QueryDSL
return queryFactory
    .select(Projections.constructor(UserDto.class,
        qUser.id, qUser.name, qUser.email))
    .from(qUser)
    .where(qUser.active.isTrue())
    .fetch();
```

## JDBC Rules (for performance-critical paths)

- Use JdbcTemplate for bulk operations and complex Oracle-specific SQL
- Use NamedParameterJdbcTemplate for readability
- Use BatchPreparedStatementSetter for batch inserts
- Always use bind variables (never string concatenation for SQL)

```java
// Named parameters
MapSqlParameterSource params = new MapSqlParameterSource()
    .addValue("status", status)
    .addValue("limit", limit);
return namedJdbcTemplate.query(sql, params, rowMapper);
```

## JUnit Test Rules

### Structure
- Test class per service/controller: UserServiceTest, UserControllerTest
- Use @SpringBootTest for integration tests
- Use @DataJpaTest for repository tests
- Use @WebMvcTest for controller tests (mocked service)
- Use Testcontainers with Oracle for DB integration tests

### Naming
- test method: should_[expected]_when_[condition]
- Example: should_throwException_when_userNotFound

### Oracle Testcontainers
```java
@Testcontainers
@DataJpaTest
class UserRepositoryTest {
    @Container
    static OracleContainer oracle = new OracleContainer("gvenzl/oracle-xe:21-slim-faststart");

    @DynamicPropertySource
    static void configure(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", oracle::getJdbcUrl);
        registry.add("spring.datasource.username", oracle::getUsername);
        registry.add("spring.datasource.password", oracle::getPassword);
    }
}
```

## JDK Version Compatibility

| Feature | JDK 8 | JDK 17 | JDK 21 |
|---------|-------|--------|--------|
| var | ❌ | ✅ | ✅ |
| record | ❌ | ✅ | ✅ |
| sealed class | ❌ | ✅ | ✅ |
| text block """ | ❌ | ✅ | ✅ |
| pattern matching switch | ❌ | Preview | ✅ |
| virtual threads | ❌ | ❌ | ✅ |
| Stream.toList() | ❌ | ✅ | ✅ |

When the JDK version is unknown, default to JDK 8 compatible code.
