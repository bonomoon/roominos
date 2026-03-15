# Expected Output Structure

```
src/main/java/com/example/
├── entity/User.java          # @Entity with JPA annotations
├── repository/UserRepository.java  # JpaRepository<User, Long>
├── service/UserService.java        # Interface
├── service/impl/UserServiceImpl.java  # @Service implementation
└── dto/UserDto.java               # Response DTO (record or class)

src/test/java/com/example/
└── service/UserServiceTest.java   # Unit tests for all 3 scenarios
```
