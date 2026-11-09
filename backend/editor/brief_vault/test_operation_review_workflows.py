"""Actual native lifecycle through durable operations, not a dispatcher whitelist."""
import pytest

from backend.editor.brief_vault import operation_reviews as ops
from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.brief_vault.test_brief_vault_develop import EVIDENCE
from backend.editor.brief_vault.test_operation_reviews import invoke, seed
from backend.editor.brief_vault.test_operation_reviews import setup as capability_setup

setup = capability_setup


def apply(service, key, **operation):
    response = invoke(service, operation, key)
    assert invoke(service, operation, key) == response
    if response["state"] == "awaiting_human":
        intent = response["result"]
        response = ops.decide(service, "draft", "draft", key, intent["digest"], "accept", "human")
        assert ops.decide(service, "draft", "draft", key, intent["digest"], "accept", "human") == response
    return response["result"]


def test_research_promote_question_answer_feedback_preserve_sources(setup):
    _, service, _ = setup
    seed(service)
    root = apply(service, "source", op="create", title="Source", text="Original", scopeNodeId="", discipline="be")["fragment"]
    research = apply(service, "research", op="research", fragmentId=root["id"], title="Feasibility", text="Literal evidence")["fragment"]
    updated = apply(service, "research-update", op="research-update", fragmentId=research["id"], expectedRevision=1,
                    note="Evidence checked", verdict="feasible", evidence=[EVIDENCE], approach="Transaction", status="done")
    assert updated["details"]["research"]["evidence"] == [EVIDENCE]
    promoted = apply(service, "promote", op="promote", fragmentId=research["id"], expectedRevision=1,
                     note="Use conclusion", text="Use one transaction")
    assert promoted["fragment"]["revision"] == 2
    question = apply(service, "question", op="question", fragmentId=root["id"], title="Downtime allowed?")["fragment"]
    pending = invoke(service, {"op": "answer", "fragmentId": question["id"], "expectedRevision": 1, "answer": "No downtime"}, "answer")
    assert pending["state"] == "awaiting_human"
    answer = ops.decide(service, "draft", "draft", "answer", pending["result"]["digest"], "accept", "human")
    assert answer["result"]["details"]["question"]["answeredBy"] == "human"
    feedback = apply(service, "feedback", op="feedback", fragmentId=root["id"], verdict="disagree", text="Measure latency")
    assert feedback["feedback"]["actor"] == "human"
    history = BriefVault(service).fragment("draft", "draft", root["id"])
    assert history["fragment"]["text"] == "Use one transaction"
    assert history["history"][0]["revision"] == 1


def test_split_mvp_discipline_and_stale_revision(setup):
    _, service, _ = setup
    seed(service)
    root = apply(service, "source", op="create", title="Two", text="First\n\nSecond", scopeNodeId="", discipline="be")["fragment"]
    split = apply(service, "split", op="split", fragmentId=root["id"], expectedRevision=1,
                  parts=[{"title": "First", "text": "First"}, {"title": "Second", "text": "Second"}])
    assert len(split["children"]) == 2
    ids = [row["id"] for row in split["children"]]
    apply(service, "propose-mvp", op="propose-mvp", fragmentIds=ids)
    apply(service, "mvp", op="set-mvp", fragmentIds=ids, mvp="yes")
    current = BriefVault(service).fragment("draft", "draft", ids[0])["fragment"]
    changed = apply(service, "discipline", op="set-discipline", fragmentId=ids[0], expectedRevision=current["revision"], discipline="ux", note="UI task")
    assert changed["fragment"]["discipline"] == "ux"
    with pytest.raises(ValueError):
        invoke(service, {"op": "revise", "fragmentId": ids[0], "expectedRevision": 1, "text": "Stale", "note": "Stale"}, "stale")


def test_unhashable_operation_is_validation_error(setup):
    from backend.canvas.payload_errors import InvalidPayload
    _, service, _ = setup
    with pytest.raises(InvalidPayload):
        invoke(service, {"op": []}, "invalid")


def test_idea_and_decision_links_use_actual_scoped_state(setup):
    client, service, _ = setup
    seed(service)
    from backend.editor.brief_vault.test_brief_vault_develop import put_state
    put_state(client, nodes={"a": {"phase": "discover", "criteria": [], "steps": [], "ideas": [
        {"id": "i1", "text": "Invalidate old cache", "by": "review", "source": "review", "at": "T", "status": "open"}]}},
        decisions=[{"id": "d1", "text": "One transaction", "pinned": False, "path": "", "nodeId": "a", "createdAt": "2026-11-09T10:00:00+00:00", "by": "human"}])
    made = apply(service, "idea", op="from-idea", nodeId="a", ideaId="i1", scopeNodeId="", discipline="be")
    assert made["idea"]["fragmentId"] == made["fragment"]["id"]
    linked = apply(service, "link", op="link-decisions", fragmentId=made["fragment"]["id"], decisionIds=["d1"])
    assert linked["details"]["decisions"] == ["d1"]
    with pytest.raises(ValueError):
        invoke(service, {"op": "link-decisions", "fragmentId": made["fragment"]["id"], "decisionIds": ["foreign"]}, "bad-link")
