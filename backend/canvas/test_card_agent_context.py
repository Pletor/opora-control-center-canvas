"""`card.fetch` a `card.fill` z knihovny (`docs/zive-zobrazeni-a-knihovna.md` §5): jen tvar, nic se nedoplňuje."""

import pytest

from backend.canvas.card_agent_context import CARD_FILL_FIELDS
from backend.canvas.graph import validate_graph


def node(card):
    return {"id": "n1", "parentId": None, "kind": "node", "name": "n1", "purpose": "", "x": 0, "y": 0, "card": card}


@pytest.mark.parametrize(
    "card",
    [
        {"fetch": {"files": ["docs/pravidla-struktury.md"]}},
        {"fetch": {"docs": ["https://example.org/a"]}},
        {"fetch": {"files": ["a.ts", "b/c.py"], "docs": ["docs/x.md"]}},
        {"fetch": {"files": [f"f{i}.ts" for i in range(20)]}},
        {"fill": ["sourceRef", "spec.acceptance"]},
        {"fill": list(CARD_FILL_FIELDS)},
        {"fill": ["spec.acceptance", "spec.steps"]},
        {"layer": "frontend", "tech": "React", "states": ["chyba"], "fetch": {"files": ["a.ts"]}, "fill": ["card.section"]},
    ],
)
def test_fetch_and_fill_in_shape_are_accepted(card):
    graph = {"nodes": [node(card)], "edges": []}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize(
    "card",
    [
        {"fetch": {}},
        {"fetch": {"files": []}},
        {"fetch": {"files": ["a.ts"], "docs": []}},
        {"fetch": {"code": ["a.ts"]}},
        {"fetch": ["a.ts"]},
        {"fetch": {"files": ["../a.ts"]}},
        {"fetch": {"files": ["/etc/passwd"]}},
        {"fetch": {"files": ["a\\b.ts"]}},
        {"fetch": {"files": ["C:/a.ts"]}},
        {"fetch": {"files": [".git/config"]}},
        {"fetch": {"files": ["https://example.org/a"]}},
        {"fetch": {"docs": ["http://example.org/a"]}},
        {"fetch": {"files": ["a.ts", "a.ts"]}},
        {"fetch": {"files": ["x" * 201]}},
        {"fetch": {"files": [f"f{i}.ts" for i in range(21)]}},
        {"fetch": {"files": [""]}},
        {"fetch": None},
        {"fill": []},
        {"fill": ["sourceRef", "sourceRef"]},
        {"fill": ["card.layer"]},
        {"fill": ["name"]},
        {"fill": "sourceRef"},
        {"fill": None},
    ],
)
def test_bad_fetch_or_fill_is_rejected(card):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [node(card)], "edges": []})


def test_spec_steps_is_fillable():
    """Rozklad stránky (`docs/architektura-pro-agenty.md` §5.2): knihovna smí agentovi říct, ať kartě navrhne kroky."""
    assert "spec.steps" in CARD_FILL_FIELDS
    assert len(CARD_FILL_FIELDS) == 12
