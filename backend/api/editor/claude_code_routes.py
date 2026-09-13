"""Rozhraní Editoru: skills Claude Code dostupné na tomto počítači a které z nich Opora vynechá."""

from fastapi import APIRouter

from backend.claude_code.skill_preferences import SkillPreferences
from backend.claude_code.skills_catalog import default_roots, list_skills
from backend.paths import REPO_ROOT


def create_claude_code_router(service, *, roots=None):
    router = APIRouter(prefix="/api/claude-code", tags=["claude-code"])
    preferences = SkillPreferences(service.root)
    skill_roots = roots or default_roots(REPO_ROOT)

    @router.get("/skills")
    def skills():
        return {"skills": list_skills(skill_roots), "disabled": preferences.disabled()}

    @router.post("/skills/disabled")
    def save_disabled(payload: dict):
        if set(payload) != {"disabled"}:
            raise ValueError("Očekáván pouze seznam disabled.")
        return {"disabled": preferences.save_disabled(payload["disabled"])}

    return router
