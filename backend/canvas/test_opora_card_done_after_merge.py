"""Steps and card acceptance added after the merge (docs/oporahub-plan-steps.md, "Kroky přidané po sloučení"):
met by the merge, visibly outside the standard process, never relaxed for an unmerged link."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_local_merge_autonomy import AGENT, HUB, STEPS, card_entry, head, ok
from backend.canvas.opora_acceptance import OporaAcceptance
from backend.canvas.opora_card_auto_close import sweep
from backend.canvas.opora_card_done import after_merge_note, card_done_state, closable, facts
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_step_results import with_after_merge
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.canvas.test_opora_card_auto_close import merged_card

LINK = {"cardId": "a", "state": "merged", "executionId": "e1", "planWrittenBack": True, "number": 22,
        "mergeSha": "787f3941234567"}
LATE = {"executionId": "e1", "number": 22, "mergeSha": "787f3941234567",
        "steps": [{"id": "s3", "title": "Doplnit dokumentaci"}, {"id": "s4", "title": "Ověřit"}], "acceptance": True}
CARD = {"steps": {"total": 4, "done": 2}, "acceptanceEvidence": False, "afterMerge": LATE}
GATE = {"reviewGate": {"status": "ready"}}


def test_merged_link_unpinned_steps_and_acceptance_are_met_by_the_merge():
    state = card_done_state(facts(CARD, LINK, GATE))
    assert state["missing"] == ["human_close"] and closable(state)
    assert state["afterMerge"] == ["steps", "card_acceptance"]
    assert state["afterMergeEvidence"] == {"executionId": "e1", "number": 22, "mergeSha": "787f3941234567",
                                           "steps": LATE["steps"]}
    assert after_merge_note(state) == ("Kroky přibyly po sloučení PR #22 (787f394) – uznány sloučením, mimo standardní"
                                       " proces: kroky: s3 Doplnit dokumentaci, s4 Ověřit; akceptace karty.")


def test_pinned_but_unreported_step_still_missing():
    # Only s3 was added after the merge; the fourth unfinished step was pinned in the merged run → blocks.
    card = {**CARD, "afterMerge": {**LATE, "steps": LATE["steps"][:1]}}
    state = card_done_state(facts(card, LINK, GATE))
    assert state["missing"] == ["steps", "human_close"] and state["afterMerge"] == ["card_acceptance"]
    assert state["afterMergeEvidence"]["steps"] == []


def test_unmerged_link_or_other_execution_changes_nothing():
    for link in ({**LINK, "state": "open", "planWrittenBack": False}, {**LINK, "executionId": "e2"}):
        state = card_done_state(facts(CARD, link, GATE))
        assert "steps" in state["missing"] and "card_acceptance" in state["missing"] and "afterMerge" not in state
    assert card_done_state({**CARD, "merged": False, "gate": {"status": "ready"}})["missing"][:2] == [
        "steps", "card_acceptance"]
    standard = card_done_state(facts({"steps": {"total": 1, "done": 1}, "acceptanceEvidence": True, "afterMerge": LATE},
                                     LINK, GATE))
    assert "afterMerge" not in standard and after_merge_note(standard) == ""


def test_items_marked_after_merge_and_current_moves():
    items = [{"id": "s1", "status": "done", "executionId": "e1"}, {"id": "s2", "status": "current", "executionId": None},
             {"id": "s3", "status": "waiting", "executionId": None}]
    value, marked = with_after_merge({"total": 3, "done": 1, "current": "s2"}, items, {"s2"})
    assert [item["status"] for item in marked] == ["done", "after_merge", "current"]
    assert value == {"total": 3, "done": 1, "current": "s3", "afterMerge": 1}
    assert with_after_merge(value, items, set()) == (value, items)


def add_steps_after_merge(service, scope, card, steps):
    changesets = OporaChangesets(service)
    current = changesets.context(scope["project"], scope["workspace"])
    document = next(item for item in current["documents"] if item["nodeId"] == card)
    fields = {**document["fields"], "steps": [*document["fields"]["steps"], *steps],
              "acceptance": document["fields"].get("acceptance", "") + " a dokumentace sedí"}
    proposal = changesets.create({**scope, "subject": "Kroky po sloučení", "parentRevision": current["acceptedHead"],
                                  "expectedGraphDigest": current["graphDigest"],
                                  "changes": [{"nodeId": card, "expectedRevision": document["revision"], "fields": fields}]},
                                 {"kind": "agent", "name": "heart"})
    OporaAcceptance(service).accept(proposal["id"], {**scope, "expectedAcceptedHead": current["acceptedHead"]},
                                    {"kind": "human", "name": "Reviewer"})


def test_steps_accepted_after_the_merge_close_the_card_with_a_trace(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        service = client.app.state.service
        scope, card, record, repo = merged_card(client, tmp_path)
        commit = head(repo)
        ok(client.post(f"{HUB}/executions/{record['executionId']}/local-merge", headers=AGENT,
                       json={**scope, "commit": commit}))
        # The plan writeback runs after the merge; the steps arrive later still (Ample #22).
        late = [{"id": "s3", "order": 3, "title": "Doplnit dokumentaci", "acceptance": ["docs sedí"], "dependsOn": ["s2"]}]
        add_steps_after_merge(service, scope, card, late)
        entry = card_entry(client, scope, card)
        assert entry["dod"]["missing"] == ["human_close"], entry["dod"]
        assert entry["dod"]["afterMerge"] == ["steps", "card_acceptance"], entry["dod"]
        assert [(item["id"], item["status"]) for item in entry["steps"]["items"]] == [
            ("s1", "done"), ("s2", "done"), ("s3", "after_merge")]
        assert entry["steps"]["done"] == len(STEPS) and entry["steps"]["current"] is None
        trail = ok(client.get(HUB + "/card-trail", params={**scope, "node": card}, headers=HEADERS))
        assert trail["afterMerge"]["requirements"] == ["steps", "card_acceptance"], trail["afterMerge"]
        assert trail["afterMerge"]["steps"] == [{"id": "s3", "title": "Doplnit dokumentaci"}]
        assert trail["afterMerge"]["mergeSha"] == commit and trail["afterMerge"]["number"] is None
        assert trail["afterMerge"]["label"].startswith(f"Kroky přibyly po lokálním sloučení ({commit[:7]})")
        assert sweep(service, scope["project"]) == [card]
        done = ok(client.get("/api/desktop-v3/state", params=scope))["state"]["nodes"][card]["done"]
        assert done["by"] == "opora" and "Kroky přibyly po lokálním sloučení" in done["note"] and "s3" in done["note"], done
