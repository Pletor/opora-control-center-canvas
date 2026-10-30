"""`member` srdce přes skutečnou aplikaci: návrh grafu mění u existujících uzlů jen `memberOf`, čeká na přijetí
člověkem a do té doby nemění přijatý ani pracovní graf; jiné úpravy uzlů a vazeb od srdce server odmítne 422."""
from urllib.parse import quote

from backend.api.brain_opora.test_heart_plan import heart, plan
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import SCOPE

__all__ = ["heart"]
PROPOSALS = opora_heart.GRAPH_PROPOSALS


def member(*flags):
    try:
        return opora_heart.run(opora_heart.parser().parse_args(["member", *flags]))
    except opora_heart.Failure as failure:
        return failure.payload


def membership(graph, node):
    return next(item for item in graph["nodes"] if item["id"] == node).get("memberOf")


def accepted_plan_with_area(call, tmp_path):
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE)["refs"]
    area = {"nodes": [{"ref": "pay", "kind": "area", "name": "Platby", "size": {"w": 400, "h": 300}}],
            "edges": []}
    done = plan(tmp_path, area)
    assert done.get("accepted") is True, done
    return refs, done["refs"]["pay"]


def test_member_proposal_waits_for_the_human_and_keeps_the_accepted_graph(heart):
    _, call, tmp_path = heart
    refs, area = accepted_plan_with_area(call, tmp_path)
    dry = member("--area", area, "--nodes", refs["mvp"], "--dry-run")
    assert dry["dryRun"] is True and dry["changes"] == [{"id": refs["mvp"], "from": None, "to": area}]
    assert len(call("GET", PROPOSALS, query=SCOPE)["items"]) == 2  # dry-run nic neposlal
    done = member("--area", area, "--nodes", refs["mvp"])
    assert done["accepted"] is False and done["proposalId"], done
    history = call("GET", PROPOSALS, query=SCOPE)["items"]
    assert sorted((item["id"] == done["proposalId"], item["accepted"]) for item in history) == [
        (False, True), (False, True), (True, False)]  # návrh členství čeká, dřívější plány přijaté
    context = call("GET", f"{PROPOSALS}/context", query=SCOPE)
    assert membership(context["acceptedGraph"], refs["mvp"]) is None  # přijatý graf beze změny
    assert membership(call("GET", "/api/view", query=SCOPE)["graph"], refs["mvp"]) is None
    # Přijetí je stejná cesta jako u jiných návrhů grafu (tady oprávněním plné autonomie místo člověka v UI).
    call("POST", f"{PROPOSALS}/{quote(done['proposalId'], safe='')}/accept",
         {**SCOPE, "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
          "adoptBaseGraphDigest": None, "reviewedChangesId": done["proposalId"]})
    assert membership(call("GET", "/api/view", query=SCOPE)["graph"], refs["mvp"]) == area
    cleared = member("--area", "none", "--nodes", f"{refs['mvp']},{refs['model']}")
    assert cleared["changes"] == [{"id": refs["mvp"], "from": area, "to": None}] and cleared["accepted"] is False


def test_member_refuses_a_non_area_target_before_sending(heart):
    _, call, tmp_path = heart
    refs, _ = accepted_plan_with_area(call, tmp_path)
    assert member("--area", refs["mvp"], "--nodes", refs["model"])["code"] == "member_area"
    assert len(call("GET", PROPOSALS, query=SCOPE)["items"]) == 2


def test_heart_graph_change_other_than_member_of_is_refused_422(heart):
    _, call, tmp_path = heart
    refs, area = accepted_plan_with_area(call, tmp_path)
    context = call("GET", f"{PROPOSALS}/context", query=SCOPE)
    base = {**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
            "subject": "Srdce"}
    edge = next(item for item in call("GET", "/api/view", query=SCOPE)["graph"]["edges"]
                if (item["source"], item["target"]) == (refs["model"], refs["cli"]))
    for bad in ({"updateNodes": [{"id": refs["mvp"], "fields": {"memberOf": area, "name": "Jinak"}}]},
                {"updateNodes": [{"id": refs["mvp"], "fields": {"parentId": None}}]},
                {"updateEdges": [{"id": edge["id"], "source": refs["cli"], "target": refs["model"], "port": "next"}]}):
        try:
            call("POST", PROPOSALS, {**base, "plan": bad})
        except opora_heart.Failure as failure:
            assert failure.payload["status"] == 422 and failure.payload["code"] == "heart_edit_scope", failure.payload
        else:
            raise AssertionError(f"Server přijal {bad}")
    assert len(call("GET", PROPOSALS, query=SCOPE)["items"]) == 2
    ok = call("POST", PROPOSALS, {**base, "plan": {"updateNodes": [{"id": refs["mvp"], "fields": {"memberOf": area}}]}})
    assert ok["accepted"] is False
