"""Real Heart identity may propose complete edits; V3 is not an acceptance grant."""
import pytest

from backend.api.brain_opora.test_heart_plan import heart, plan
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import SCOPE

__all__ = ["heart"]


def test_real_heart_complete_plan_is_pending_and_verified(heart):
    _, call, tmp_path = heart
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")["refs"]
    before = call("GET", opora_heart.GRAPH_PROPOSALS + "/context", query=SCOPE)
    revision = call("GET", "/api/desktop-v3/state", query=SCOPE)["revision"]
    raw = {"draftVersion": 3, "updateNodes": [{"id": refs["model"], "fields": {"name": "Proposed name"}}],
        "extend": [{"node": "@" + refs["model"], "expectedRevision": revision,
                    "text": {"expectedRevision": 0, "text": "Pending implementation instructions"},
                    "blocks": [{"ref": "check", "title": "Check", "ports": [{"ref": "yes"}]}]}],
        "edges": [{"from": "@" + refs["model"], "to": "@" + refs["cli"], "port": "block", "block": "check", "blockPort": "yes"}]}
    result = plan(tmp_path, raw)
    assert result["persisted"] and result["verified"] and not result["accepted"], result
    saved = call("GET", opora_heart.GRAPH_PROPOSALS + "/" + result["proposalId"], query=SCOPE)
    assert saved["schemaVersion"] == 3 and saved["contentEffects"]["documents"][0]["value"] == "Pending implementation instructions"
    assert call("GET", opora_heart.GRAPH_PROPOSALS + "/context", query=SCOPE)["acceptedHead"] == before["acceptedHead"]
    assert call("GET", "/api/view", query=SCOPE)["graph"] == before["workingGraph"]
    for fields in ({"parentId": "absent"}, {"parentId": refs["model"]}):
        with pytest.raises(opora_heart.Failure):
            call("POST", opora_heart.GRAPH_PROPOSALS, {**SCOPE, "subject": "Invalid parent",
                "parentRevision": before["acceptedHead"], "expectedGraphDigest": before["graphDigest"],
                "plan": {"draftVersion": 3, "updateNodes": [{"id": refs["model"], "fields": fields}]}})
