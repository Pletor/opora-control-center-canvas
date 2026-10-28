"""Kdo smí psát úkoly a odpovídat na lístky (docs/brain-heart.md §5): člověk, nebo srdce téhož projektu.

Srdce pozná jen middleware `boundary`: po ověření tokenu srdce zdí nastaví `request.state.heart_project`.
Hlavička ani tělo požadavku ho podvrhnout nemůže; bez ověřeného tokenu je hodnota prázdná.
"""
from backend.canvas.activity_log import HumanRequired


def heart_project(request):
    """Projekt, pro který zeď ověřila token srdce; jinak prázdný text."""
    value = getattr(request.state, "heart_project", "")
    return value if isinstance(value, str) else ""


def writer(request, project, message):
    """`"human"` nebo `"heart"` (srdce jen ve svém projektu); jinak `HumanRequired` (403 agentovi)."""
    if request.state.actor == "human":
        return "human"
    if project and heart_project(request) == project:
        return "heart"
    raise HumanRequired(request.state.actor, message)
