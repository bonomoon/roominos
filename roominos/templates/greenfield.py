"""Greenfield skill — create new Spring Boot project from spec."""
from .base import BaseSkill


class GreenfieldSkill(BaseSkill):
    name = "greenfield"
    description = "Create a new Spring Boot application from requirements"

    def analyze_system(self) -> str:
        return "You are a requirements analyst. Extract entities, relationships, API endpoints, and business rules from the spec."

    def plan_system(self) -> str:
        return (
            "You are a Java architect. Plan a Spring Boot 3.2 project.\n"
            "Order: pom.xml → entities → repositories → services → controllers → DTOs → config → tests\n"
            "1-2 files per batch. Output as JSON array."
        )

    def implement_system(self) -> str:
        return (
            "You are a Java developer. Create Spring Boot 3.2 code.\n"
            "Rules: jakarta.persistence, @SequenceGenerator for Oracle, BigDecimal for money,\n"
            "constructor injection, @Transactional on services.\n"
            "Output ONLY Java code. No explanation."
        )

    def verify_criteria(self) -> list[str]:
        return [
            "Entity classes use @SequenceGenerator",
            "BigDecimal for monetary fields",
            "jakarta.persistence imports",
            "No hardcoded Hibernate dialect",
            "application-test.yml with H2",
            "Constructor injection (not field)",
            "@Transactional on services",
            "@SpringBootTest on test classes",
            "REST endpoints follow /api/v1/ pattern",
            "Input validation with @Valid",
        ]

    def mandatory_files(self) -> list[dict]:
        return [
            {"path": "src/main/resources/application.yml", "description": "Spring config, NO hardcoded dialect", "type": "config"},
            {"path": "src/test/resources/application-test.yml", "description": "H2 test config", "type": "config"},
            {"path": "pom.xml", "description": "Maven build with Spring Boot 3.2", "type": "config"},
        ]
