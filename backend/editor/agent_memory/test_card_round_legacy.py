"""Kola karty jsou zrušená (rozhodnutí vlastníka 23. 10.): žádné routy, brief bez kol, starší `round` se nemění."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.card_round_legacy import guard_state_write, validate_round
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE, install_graph, node

ROUND = {"number": 2, "openedAt": "2026-10-09T10:00:00+00:00", "by": "human", "reason": "nové zadání"}


def test_round_routes_are_gone_and_brief_has_no_rounds(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("c1", "s1")], "edges": []})
        assert client.post("/api/desktop-v3/card-round", headers=HEADERS, json={**SCOPE, "nodeId": "c1"}).status_code in (404, 405)
        assert client.get("/api/desktop-v3/card-rounds", params={**SCOPE, "nodeId": "c1"}).status_code in (404, 405)
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"})
        assert brief.status_code == 200, brief.text
        assert "rounds" not in brief.json() and "previousRounds" not in brief.json()
        assert not {"rounds.brief.fragments", "previousRounds"} & set(brief.json()["trust"]["dataFromAgents"])


def test_legacy_round_keeps_its_shape_and_never_changes():
    assert validate_round(dict(ROUND), "c1") == ROUND
    with pytest.raises(ValueError):
        validate_round({**ROUND, "number": 1}, "c1")
    before = {"nodes": {"c1": {"round": ROUND}}}
    guard_state_write("human", before, {"nodes": {"c1": {"round": ROUND}}})
    with pytest.raises(ValueError, match="zrušená"):
        guard_state_write("human", before, {"nodes": {"c1": {"round": {**ROUND, "number": 3}}}})
    with pytest.raises(ValueError, match="zrušená"):
        guard_state_write("human", {"nodes": {"c1": {}}}, before)
