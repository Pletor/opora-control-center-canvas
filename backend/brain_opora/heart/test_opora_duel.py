"""Duel srdce (docs/brain-heart.md §3c) bez procesu: pravidlo výsledku zrcadlí server. Celý průběh duelu přes
skutečnou aplikaci je v `backend/api/brain_opora/test_heart_research.py`."""
from backend.brain_opora.heart import opora_duel


def test_outcome_rule_mirrors_the_server():
    assert opora_duel.outcome_of(0.8, 3) == "adopt" and opora_duel.outcome_of(0.8, 2) == "synthesis"
    assert opora_duel.outcome_of(0.4, 5) == "keep" and opora_duel.outcome_of(0.5, 5) == "synthesis"
