"""Tests for skill system."""
import pytest
from roominos.templates.base import BaseSkill
from roominos.templates.registry import get_skill, list_skills, SKILLS


def test_all_skills_implement_interface():
    for name, cls in SKILLS.items():
        skill = cls()
        assert isinstance(skill, BaseSkill)
        assert skill.name == name
        assert len(skill.analyze_system()) > 0
        assert len(skill.plan_system()) > 0
        assert len(skill.implement_system()) > 0
        assert len(skill.verify_criteria()) > 0


def test_get_skill():
    skill = get_skill("migration")
    assert skill.name == "migration"


def test_get_skill_unknown():
    with pytest.raises(ValueError):
        get_skill("unknown")


def test_list_skills():
    skills = list_skills()
    assert len(skills) == 5
    names = [s["name"] for s in skills]
    assert "migration" in names
    assert "greenfield" in names


def test_migration_mandatory_files():
    skill = get_skill("migration")
    files = skill.mandatory_files()
    paths = [f["path"] for f in files]
    assert any("application.yml" in p for p in paths)
    assert any("application-test.yml" in p for p in paths)
