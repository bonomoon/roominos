"""Skill registry — discover and load skills."""
from .base import BaseSkill
from .migration import MigrationTemplate
from .greenfield import GreenfieldSkill
from .refactor import RefactorSkill
from .test_gen import TestGenSkill
from .review import ReviewSkill

SKILLS: dict[str, type[BaseSkill]] = {
    "migration": MigrationTemplate,
    "greenfield": GreenfieldSkill,
    "refactor": RefactorSkill,
    "test-gen": TestGenSkill,
    "review": ReviewSkill,
}


def get_skill(name: str, **kwargs) -> BaseSkill:
    if name not in SKILLS:
        available = ", ".join(SKILLS.keys())
        raise ValueError(f"Unknown skill: {name}. Available: {available}")
    return SKILLS[name](**kwargs)


def list_skills() -> list[dict]:
    return [{"name": s.name, "description": s.description} for s in [cls() for cls in SKILLS.values()]]
