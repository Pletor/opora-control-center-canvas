from copy import deepcopy

import pytest

from backend.canvas.test_opora_changesets import AGENT, HUMAN, baseline, service
from backend.editor.node import removal_reviews as reviews

__all__ = ["service"]


def data(service, target="a"):
    preview = service.removals.preview("draft", "draft", "node", target)
    return {"kind": "node", "target": target, "digest": preview["digest"], "confirmed": True}


def prepare(service, body=None, key="remove"):
    return reviews.prepare(service, "draft", "draft", "remove_item", body or data(service), key, AGENT)


def test_agent_native_remove_restore_full_readback_and_replay(service):
    before = deepcopy(service.view("draft", "draft")["graph"])
    body = data(service)
    result = prepare(service, body)
    assert result["verified"] and result["acceptedHead"] is None
    assert prepare(service, body) == result
    restore = {"recoveryId": result["result"]["recoveryId"], "digest": service.view("draft", "draft")["digest"]}
    restored = reviews.prepare(service, "draft", "draft", "restore_removed", restore, "restore", AGENT)
    assert restored["verified"]
    assert service.view("draft", "draft")["graph"] == before
    assert reviews.prepare(service, "draft", "draft", "restore_removed", restore, "restore", AGENT) == restored


def test_accepted_plan_requires_review_and_keeps_accepted_authority(service):
    baseline(service)
    before = deepcopy(service.view("draft", "draft")["graph"])
    prepared = prepare(service)
    assert prepared["state"] == "awaiting_human" and not prepared["applied"]
    assert service.view("draft", "draft")["graph"] == before
    with pytest.raises(ValueError, match="human"):
        reviews.apply(service, "draft", "draft", "remove_item", "remove", AGENT)
    result = reviews.apply(service, "draft", "draft", "remove_item", "remove", HUMAN)
    assert result["acceptedHead"] == prepared["review"]["acceptedHead"]
    assert not result["acceptedPlanChanged"]
    assert reviews.apply(service, "draft", "draft", "remove_item", "remove", HUMAN) == result
    assert reviews.read(service, "draft", "draft", "remove_item", "remove")["application"]["status"] == "complete"


def test_stale_review_foreign_scope_and_changed_request_rejected(service):
    baseline(service)
    body = data(service)
    prepare(service, body)
    with pytest.raises(Exception, match="different request"):
        prepare(service, {**body, "target": "b"})
    with pytest.raises(ValueError, match="not found"):
        reviews.read(service, "draft", "main", "remove_item", "remove")
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    graph["nodes"][0]["x"] += 10
    service.save_graph("draft", "draft", graph, view["digest"])
    with pytest.raises(ValueError, match="stale"):
        reviews.apply(service, "draft", "draft", "remove_item", "remove", HUMAN)
    assert service.view("draft", "draft")["graph"] == graph


def test_partial_native_recovery_capture_is_not_repeated(service, monkeypatch):
    body = data(service)
    monkeypatch.setattr(service, "save_graph", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("injected")))
    with pytest.raises(ValueError, match="remove.*uncertain"):
        prepare(service, body)
    db = service.db_for("draft")
    assert db.execute("SELECT count(*) FROM removal_restores").fetchone()[0] == 1
    with pytest.raises(Exception, match="incomplete"):
        prepare(service, body)
    assert db.execute("SELECT count(*) FROM removal_restores").fetchone()[0] == 1
