"""Full native placement and outer uncertainty after a checkpoint or committed graph."""
import pytest

from backend.canvas.payload_errors import NextStep
from backend.editor.brief_vault import operation_reviews as ops
from backend.editor.brief_vault.test_brief_vault_gates import PAYLOADS, root, vault_client, walk
from backend.editor.brief_vault.test_operation_review_workflows import apply
from backend.editor.brief_vault.test_operation_reviews import invoke


def test_full_gate_cycle_proposals_placement_and_lessons(tmp_path):
    with vault_client(tmp_path) as client:
        service = client.app_state.service
        fragment = root(client)
        fragment = apply(service, "scoped", op="gate", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate="scoped", value=True, note="scope")["fragment"]
        proposal = apply(service, "propose", op="propose", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate="weighed", payload=PAYLOADS["weighed"], note="Evidence")
        rejected = apply(service, "reject-proposal", op="reject-proposal", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate="weighed", note="Needs broader evidence")
        assert rejected["rejected"]["id"] == proposal["proposal"]["id"]
        assert rejected["rejected"]["status"] == "rejected"
        for name in ("weighed", "synthesized", "decided", "planned", "placed", "verified", "learned"):
            extra = {"payload": PAYLOADS[name]} if name in PAYLOADS else {}
            if name == "verified":
                extra = {"payload": {"actual": {"tests": "pass", "criticRounds": 1, "unexpected": False}}}
            if name == "learned":
                extra = {"payload": {"lesson": "Keep imports atomic", "kind": "pattern"}}
            result = apply(service, name, op="gate", fragmentId=fragment["id"], expectedRevision=fragment["revision"], gate=name, value=True, note=name, **extra)
            fragment = result["fragment"]
            if name == "placed":
                refs = result["placement"]["refs"]
                from backend.editor.brief_vault.brief_vault import BriefVault
                state = BriefVault(service).state.current("draft", "draft")["state"]["nodes"]
                assert state[refs["f1"]]["fragmentRefs"][0]["fragmentId"] == fragment["id"]
                assert len(state[refs["f1"]]["blocks"]) == 4
                assert service.texts.read(("draft", "draft", refs["f1"]))["text"]
        lesson = result["lesson"]
        confirmed = apply(service, "confirm", op="confirm-lesson", lessonId=lesson["id"], note="Still useful")
        assert confirmed["lesson"]["revision"] == lesson["revision"] + 1
        dropped = apply(service, "drop", op="drop-lesson", lessonId=lesson["id"], note="Superseded")
        assert dropped["lesson"]["dropped"] and dropped["lesson"]["actor"] == lesson["actor"]
        event = service.db_for("draft").execute("SELECT actor FROM brief_lesson_events WHERE lesson_id=? AND kind='drop'", (lesson["id"],)).fetchone()
        assert event[0] == "human"


@pytest.mark.parametrize("point", ["after_checkpoint", "after_graph"])
def test_placement_failure_is_pending_and_cannot_repeat(tmp_path, monkeypatch, point):
    from backend.canvas import operation_readback
    from backend.editor.brief_vault import brief_vault_placement as placement
    with vault_client(tmp_path) as client:
        service = client.app_state.service
        fragment = walk(client, root(client), "planned")
        command = {"op": "gate", "fragmentId": fragment["id"], "expectedRevision": fragment["revision"], "gate": "placed", "value": True, "note": "Place exact plan"}
        pending = invoke(service, command, "place")
        calls = []
        def fail(*args, **kwargs):
            calls.append(True)
            raise OSError(point)
        if point == "after_checkpoint":
            monkeypatch.setattr(placement, "apply_plan", fail)
        else:
            monkeypatch.setattr(operation_readback, "verify_plan", fail)
        with pytest.raises(NextStep, match="place.*uncertain"):
            ops.decide(service, "draft", "draft", "place", pending["result"]["digest"], "accept", "human")
        before = service.view("draft", "draft")["digest"]
        with pytest.raises(NextStep, match="incomplete"):
            ops.decide(service, "draft", "draft", "place", pending["result"]["digest"], "accept", "human")
        assert len(calls) == 1
        assert service.view("draft", "draft")["digest"] == before
        assert ops.read(service, "draft", "draft", "place")["decision"]["status"] == "pending"
