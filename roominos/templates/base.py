"""Base skill interface for Roominos pipeline."""
from abc import ABC, abstractmethod


class BaseSkill(ABC):
    """All skills must implement these methods."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @abstractmethod
    def analyze_system(self) -> str:
        """System prompt for analyze stage."""
        ...

    @abstractmethod
    def plan_system(self) -> str:
        """System prompt for plan stage."""
        ...

    @abstractmethod
    def implement_system(self) -> str:
        """System prompt for implement stage."""
        ...

    @abstractmethod
    def verify_criteria(self) -> list[str]:
        """Acceptance criteria for judge."""
        ...

    def mandatory_files(self) -> list[dict]:
        """Files that must always be in the plan."""
        return []

    def reflect_checks(self) -> list[str]:
        """Additional patterns to check in reflect stage."""
        return []
