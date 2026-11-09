"""Complete acceptance writes SQL graph authority; Git source stays untouched on rollback."""
from copy import deepcopy

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_change_acceptance import OporaGraphChangeAcceptance
from backend.canvas.test_opora_changesets import HUMAN
from backend.canvas.test_opora_graph_change_git import edit
from backend.canvas.test_opora_graph_complete import full_plan
from backend.canvas.test_opora_graph_git import git_graphs, prepared
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.opora_changesets import ChangesetRepository

__all__ = ["git_graphs"]


def test_complete_git_rolls_back_all_authoritative_stores_then_retries(git_graphs, monkeypatch):
    service, scope, original, data = git_graphs
    item, payload = prepared(service, scope)
    baseline = OporaGraphAcceptance(service).accept(item["id"], payload, HUMAN)
    complete, payload = edit(service, scope, full_plan())
    payload["adoptBaseContentDigest"] = complete["contentBase"]["digest"]
    before = deepcopy(service.view(*scope.values())["graph"])
    state = deepcopy(DesktopV3State(service).current(**scope))
    with monkeypatch.context() as patch:
        def fail(*args):
            raise RuntimeError("after all stores before accepted head")
        patch.setattr(ChangesetRepository, "advance", fail)
        with pytest.raises(RuntimeError, match="after all stores"):
            OporaGraphChangeAcceptance(service).accept(complete["id"], payload, HUMAN)
    assert service.view(*scope.values())["graph"] == before
    assert DesktopV3State(service).current(**scope) == state
    assert ChangesetRepository(service.db_for(scope["project"]), **scope).head() == baseline["id"]
    for node in complete["refs"].values():
        assert service.specs.read((*scope.values(), node))["revision"] == 0
        assert service.texts.read((*scope.values(), node))["revision"] == 0
    assert service.graph_file(*scope.values()).read_bytes() == original
    result = OporaGraphChangeAcceptance(service).accept(complete["id"], payload, HUMAN)
    fresh = CanvasService(data)
    try:
        assert fresh.view(*scope.values())["graph"] == complete["resultGraph"]
        assert fresh.texts.read((*scope.values(), complete["refs"]["source"]))["text"] == "Exact proposed text"
        assert OporaGraphChangeAcceptance(fresh).accept(complete["id"], payload, HUMAN) == result
        assert fresh.graph_file(*scope.values()).read_bytes() == original
    finally:
        fresh.close()
