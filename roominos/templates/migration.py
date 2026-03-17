"""Migration template — Pro*C to Java/Spring domain-specific prompts."""


class MigrationTemplate:
    """Injects domain-specific prompts for Pro*C → Java/Spring migration."""

    def __init__(self, target_stack: str = "Spring Boot 3.2, JDK 17, Spring Data JPA, Oracle"):
        self.target_stack = target_stack

    def analyze_system(self) -> str:
        return (
            "You are a legacy code analyst specializing in C/Pro*C to Java migration. "
            "Identify: functions, EXEC SQL statements, cursor patterns, host variables, "
            "error handling (GOTO/WHENEVER), global variables, and data types."
        )

    def plan_system(self) -> str:
        return (
            f"You are a Java architect planning a migration to {self.target_stack}. "
            "Create a file-by-file migration plan. Rules:\n"
            "- 1-2 files per batch\n"
            "- Order: pom.xml → Entity → Repository → Service → Config → Test\n"
            "- Every table needs an @Entity with @SequenceGenerator\n"
            "- Every EXEC SQL needs a JPA method or @Query\n"
            "- Every GOTO/WHENEVER needs an exception mapping\n"
            "Output as JSON array: [{\"path\": \"...\", \"description\": \"...\", \"type\": \"...\"}]"
        )

    def implement_system(self) -> str:
        return (
            f"You are a Java developer creating {self.target_stack} code. Rules:\n"
            "- jakarta.persistence (NOT javax)\n"
            "- @SequenceGenerator for Oracle (NOT GenerationType.IDENTITY)\n"
            "- BigDecimal for ALL monetary/decimal fields\n"
            "- Constructor injection (NOT @Autowired field injection)\n"
            "- @Transactional on service methods\n"
            "- Lombok @Data, @Builder for entities\n"
            "Output ONLY Java code. No explanation. No markdown fences."
        )

    def verify_criteria(self) -> list[str]:
        """Default acceptance criteria for migration verification."""
        return [
            "Entity classes use @SequenceGenerator (not IDENTITY)",
            "All monetary fields use BigDecimal (not double/float)",
            "jakarta.persistence imports (not javax.persistence)",
            "No Hibernate dialect hardcoded in config",
            "application-test.yml exists with H2 datasource",
            "Service uses constructor injection",
            "@Transactional on service methods",
            "Test class exists with @SpringBootTest",
        ]
