"""`steps` srdce přes skutečnou aplikaci: tenká karta (krátký výslech) dostane kroky návrhem změny zadání
(`/api/oporahub/changesets`). Při plné autonomii ho srdce samo přijme a měřák karty už nehlásí `evidence: thin`;
bez autonomie návrh čeká na člověka a přijaté zadání zůstane beze změny. Graf se nemění."""
import json

from backend.api.brain_opora.test_heart_plan import heart, plan
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import HEADERS, SCOPE

__all__ = ["heart"]
STEPS = {"goal": "python ukoly.py export zapíše úkoly do CSV.",
         "steps": [{"title": "Export do CSV", "kind": "code", "files": ["ukoly.py"],
                    "acceptance": ["python ukoly.py export vytvoří ukoly.csv"]},
                   {"title": "Test exportu", "kind": "test", "files": ["test_export.py"],
                    "acceptance": ["test_export.py ověří hlavičku a řádky"]}]}


def thin_card(tmp_path):
    """Přijatý plán ze vzoru a k němu tenká karta (jeden krok bez souborů), jakou budí krátký výslech."""
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE, "--accept")["refs"]
    step = [{"id": "s1", "order": 1, "title": "Export", "dependsOn": [], "acceptance": ["export funguje"]}]
    more = {"nodes": [{"ref": "export", "kind": "node", "parent": "@" + refs["mvp"], "name": "[task] Export do CSV",
                       "purpose": "Úkoly do souboru.", "card": {"layer": "backend", "status": "ready"},
                       "spec": {"goal": "Export.", "non_goals": "", "acceptance": "", "steps": step}}],
            "edges": []}
    done = plan(tmp_path, more, "--accept")
    assert done.get("accepted") is True, done
    return done["refs"]["export"]


def steps(tmp_path, node, *flags, body=STEPS):
    (tmp_path / "steps.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    try:
        return opora_heart.run(opora_heart.parser().parse_args(["steps", "--node", node, "--file", "steps.json", *flags]))
    except opora_heart.Failure as failure:
        return failure.payload


def card_of(call, node):
    state = call("GET", "/api/oporahub/agent-state", query=SCOPE)
    return next(card for card in state["cards"] if card["nodeId"] == node)


def accepted_fields(call, node):
    context = call("GET", "/api/oporahub/changesets/context", query=SCOPE)
    return next(item["fields"] for item in context["acceptedDocuments"] if item["nodeId"] == node)


def autonomy(client, full):
    """Přepínač plné autonomie smí jen člověk (doklad UI); srdce pak zase běží bez cookies."""
    client.get("/api/access/ui-session", headers={**HEADERS, "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors"})
    response = client.post("/api/project-settings/agent-autonomy", headers=HEADERS,
                           json={"project": SCOPE["project"], "full": full})
    assert response.status_code == 200, response.text
    client.cookies.clear()


def test_steps_with_full_autonomy_fill_the_thin_card_and_clear_the_gauge(heart):
    client, call, tmp_path = heart
    node = thin_card(tmp_path)
    assert card_of(call, node)["gauge"]["evidence"] == "thin"
    graph = call("GET", "/api/view", query=SCOPE)["digest"]
    autonomy(client, True)
    dry = steps(tmp_path, node, "--dry-run")
    assert dry["dryRun"] is True and dry["stepsBefore"] == 1 and dry["steps"] == ["s1", "s2"], dry
    assert call("GET", "/api/oporahub/changesets", query=SCOPE)["items"] == []  # dry-run nic neposlal
    done = steps(tmp_path, node)
    assert done["accepted"] is True and done["proposalId"] and done["path"] == "spec-changeset", done
    fields = accepted_fields(call, node)
    assert [(item["id"], item["kind"], item["files"]) for item in fields["steps"]] == [
        ("s1", "code", ["ukoly.py"]), ("s2", "test", ["test_export.py"])]
    assert fields["goal"] == STEPS["goal"] and fields["non_goals"] == ""  # ostatní pole zadání zůstala
    card = card_of(call, node)
    assert card["gauge"]["evidence"] == "ok" and card["gauge"]["files"] == 2, card["gauge"]
    assert call("GET", "/api/view", query=SCOPE)["digest"] == graph  # graf beze změny
    history = call("GET", "/api/oporahub/changesets", query=SCOPE)["items"]
    assert [(item["by"], item["accepted"]) for item in history] == [({"kind": "agent", "name": "heart"}, True)]


def test_steps_without_autonomy_wait_for_the_human(heart):
    _, call, tmp_path = heart
    node = thin_card(tmp_path)
    done = steps(tmp_path, node)
    assert done["accepted"] is False and done["proposalId"] and "člověk" in done["hint"], done
    assert len(accepted_fields(call, node)["steps"]) == 1  # přijaté zadání beze změny
    assert card_of(call, node)["gauge"]["evidence"] == "thin"
    offered = [action for action in call("GET", "/api/oporahub/agent-state", query=SCOPE)["actions"]
               if action["verb"] == "accept" and action["targetId"] == done["proposalId"]]
    assert offered and offered[0]["blockReason"] == "human_only"


def test_steps_refuse_unknown_cards_and_server_shape_errors(heart):
    _, call, tmp_path = heart
    node = thin_card(tmp_path)
    assert steps(tmp_path, "n_missing")["code"] == "steps_unknown_node"
    bad = {"steps": [{**STEPS["steps"][0], "acceptance": []}, STEPS["steps"][1]]}  # tvar kroku hlídá server
    refused = steps(tmp_path, node, body=bad)
    assert refused["status"] in (400, 409, 422) and "oporahub-plan-steps" in refused["hint"], refused
    assert call("GET", "/api/oporahub/changesets", query=SCOPE)["items"] == []
