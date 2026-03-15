# Verification: Spring Task 002 - QueryDSL Search

## Acceptance Criteria

### Setup
- [ ] QueryDSL dependencies in pom.xml (querydsl-jpa, querydsl-apt)
- [ ] APT plugin configured for Q-class generation
- [ ] Q-classes generate successfully: mvn compile

### Implementation
- [ ] SearchCriteria DTO with all optional fields
- [ ] Custom repository using JPAQueryFactory
- [ ] BooleanBuilder dynamically adds conditions for non-null criteria
- [ ] DTO projection via Projections.constructor()
- [ ] Pagination via QueryResults or count + fetch

### API
- [ ] GET /api/v1/products/search?name=&minPrice=&maxPrice=&category=&page=&size=&sort=
- [ ] Empty criteria returns all products (paginated)
- [ ] Multiple criteria AND-combined

### Tests
- [ ] Test: no filters → all results
- [ ] Test: name filter only → correct subset
- [ ] Test: price range → correct subset
- [ ] Test: combined filters → correct intersection
- [ ] Test: pagination works with filters
- [ ] All tests pass: mvn test
