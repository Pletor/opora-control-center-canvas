"""One authenticated Heart remains one principal across explicit simulated roles."""
import pytest

from backend.editor.brief_vault import operation_reviews as ops
from backend.editor.brief_vault.test_operation_review_workflows import apply
from backend.editor.brief_vault.test_operation_reviews import SESSION, seed
from backend.editor.brief_vault.test_operation_reviews import setup as capability_setup

setup = capability_setup


def test_delegated_duel_and_vision_are_native_records_not_human_approval(setup):
    _, service, _ = setup
    seed(service)
    apply(service, "vision", op="vision-set", scopeNodeId="", text="Reliable imports", note="Initial human vision")
    root = apply(service, "source", op="create", scopeNodeId="", title="Import", text="CSV", discipline="be")["fragment"]
    opened = apply(service, "duel", op="duel-open", subject={"kind": "fragment", "id": root["id"]}, scopeNodeId="",
                   incumbent={"text": "CSV"}, challenger={"text": "JSON"}, delegatedRoles=True)
    fragment = opened["fragment"]
    assert opened["duel"]["delegation"]["principal"] == "heart"
    assert opened["duel"]["delegation"]["mode"] == "single-principal-role-simulation"
    claims = []
    for index in range(3):
        claim = apply(service, f"claim-{index}", op="duel-turn", fragmentId=fragment["id"], expectedRevision=fragment["revision"],
                      side="B", kind="claim", text=f"JSON evidence {index}", delegateRole="advocate_b")
        fragment = claim["fragment"]
        claims.append(claim["turn"]["id"])
    for index, claim in enumerate(claims):
        scored = apply(service, f"score-{index}", op="duel-score", fragmentId=fragment["id"], expectedRevision=fragment["revision"],
                       turnId=claim, strength=10, supports="B", delegateRole="judge_1")
        assert scored["score"]["judge"] == "heart"
        fragment = scored["fragment"]
    decided = apply(service, "decide", op="duel-decide", fragmentId=fragment["id"], expectedRevision=fragment["revision"])
    assert decided["decision"]["outcome"] == "adopt"
    alignment = {"op": "vision-align", "scopeNodeId": "", "duelId": fragment["id"], "score": 9, "note": "Goal", "delegateRole": "judge_2"}
    from backend.editor.brief_vault.brief_vault_model import BadRequest
    for number, (session, command) in enumerate([
        (SESSION, {key: value for key, value in alignment.items() if key != "delegateRole"}),
        (SESSION, {**alignment, "delegateRole": "advocate_b"}),
        ({**SESSION, "id": "foreign-session"}, alignment),
        ({**SESSION, "role": "worker"}, alignment),
    ]):
        with pytest.raises(BadRequest):
            ops.invoke(service, "draft", "draft", session, command, f"invalid-align-{number}")
    aligned = apply(service, "align", op="vision-align", scopeNodeId="", duelId=fragment["id"], score=9,
                    note="Matches reliability goal", delegateRole="judge_2")
    assert aligned["point"]["by"] == "heart"
    from backend.canvas.opora_changesets import OporaChangesets
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] is None
    with pytest.raises(ValueError):
        ops.invoke(service, "draft", "draft", {**SESSION, "id": "different-session"},
                   {"op": "duel-decide", "fragmentId": fragment["id"], "expectedRevision": fragment["revision"]}, "decide")
