"""Řazení oddílů plátna pro asistenta (RLM, docs/asistent.md §13.3); jen loopback.

Tenký router nad `backend.claude_code.assistant.rlm_rank`. Klíč Jev se čte při každém dotazu
z `key_source` (nastavení aplikace), zůstává v backendu a do odpovědi ani do procesu `claude`
se nedostane. Hranici tunelu drží `backend/app/remote_access.py`.
"""

from fastapi import APIRouter

from backend.claude_code.assistant.rlm_rank import rank
from backend.integrations.typesafe_client import evaluate as typesafe_evaluate

RANK_KEYS = {"project", "workspace", "query", "candidates", "top"}


def _scope(value, label):
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError(f"{label} musí být neprázdný text do 200 znaků.")


def create_rlm_router(*, key_source=lambda: None, evaluate=typesafe_evaluate):
    router = APIRouter(prefix="/api/rlm", tags=["rlm"])

    @router.post("/rank")
    def rank_sections(payload: dict):
        if not isinstance(payload, dict) or set(payload) != RANK_KEYS:
            raise ValueError("Řazení vyžaduje přesně pole " + ", ".join(sorted(RANK_KEYS)) + ".")
        _scope(payload["project"], "project")
        _scope(payload["workspace"], "workspace")
        key = key_source()
        return rank(payload["query"], payload["candidates"], payload["top"],
                    evaluate=lambda state, questions: evaluate(state, questions, key=key))

    return router
