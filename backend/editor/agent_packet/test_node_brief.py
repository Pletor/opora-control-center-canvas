"""Balíček karty pro model: jeden JSON, který se čte odshora dolů (opora.node-brief/1)."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}


def branch(kind="none", target="", note=""):
    return {"kind": kind, "targetId": target, "note": note}


def block(bid, number, **overrides):
    item = {
        "id": bid, "number": number, "title": f"Blok {number}", "text": "", "tags": [], "todos": [], "images": [],
        "state": {"status": "open", "condition": "", "onMet": branch(), "onUnmet": branch()},
        "parentBlockId": "",
    }
    item.update(overrides)
    return item


def report(**overrides):
    item = {
        "log": "Založil jsem router.", "summary": "Router hotový.", "handoff": "Pokrač u testu.",
        "improvements": "Chybí fixture.", "errors": "", "updatedAt": "2026-09-14T08:00:00+00:00",
        "by": "agent", "agent": "sonnet",
    }
    item.update(overrides)
    return item


GRAPH = {
    "nodes": [
        {"id": "sektor", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "Celek", "x": 0, "y": 0},
        {"id": "focus", "parentId": "sektor", "kind": "node", "name": "Ohnisko", "purpose": "Podstata", "x": 0, "y": 0},
        {"id": "dite", "parentId": "focus", "kind": "node", "name": "Dítě", "purpose": "", "x": 0, "y": 200},
        {"id": "pred", "parentId": "sektor", "kind": "node", "name": "Předchůdce", "purpose": "", "x": -300, "y": 0},
        {"id": "dalsi", "parentId": "sektor", "kind": "node", "name": "Další", "purpose": "", "x": 300, "y": 0},
    ],
    "edges": [
        {"id": "e-in", "source": "pred", "target": "focus", "port": "next"},
        {"id": "e-out", "source": "focus", "target": "dalsi", "port": "block",
         "sourceBlockId": "b1", "sourcePortId": "p1"},
    ],
}


def seed_graph(client):
    view = client.get("/api/view", params=SCOPE).json()
    saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": GRAPH, "digest": view["digest"]})
    assert saved.status_code == 200, saved.text


def save_state(client, state, expected=0):
    saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                        json={**SCOPE, "expectedRevision": expected, "state": state})
    assert saved.status_code == 200, saved.text
    return saved.json()


def full_state():
    return {
        **EMPTY,
        "rules": [{"id": "r1", "text": "Nikdy nespouštět model.", "kind": "must_not",
                   "scope": "project", "target": ""}],
        "decisions": [{"id": "d1", "text": "Strom 1:1.", "pinned": True, "path": "", "nodeId": "",
                       "createdAt": "2026-09-11T08:00:00+00:00", "by": "human"}],
        "nodes": {"focus": {
            "phase": "build",
            # Fáze, kritéria a kroky jsou tolerovaná stará data: stav je uloží, brief je nenese.
            "criteria": [{"id": "c1", "text": "Testy zelené", "checked": True}],
            "steps": [{"id": "s1", "text": "Napsat test", "assignee": "builder", "done": False}],
            "actions": [{"id": "a1", "pipelineId": "verify.run-tests", "label": "Testy", "params": {}}],
            "rules": [{"id": "nr1", "text": "Nesahat na frontend.", "kind": "must_not"}],
            "materials": [{"id": "m1", "kind": "link", "path": "https://example.com/spec", "caption": "Spec"}],
            "blocks": [
                block("b2", "2", title="Druhý"),
                block("b1", "1", title="První", text="Obsah",
                      state={"status": "open", "condition": "Testy zelené",
                             "onMet": branch(), "onUnmet": branch()},
                      ports=[{"id": "p1", "label": "Návrh API"}, {"id": "p2", "label": "Oprava"}]),
            ],
        }},
        "edges": {"e-in": report(), "e-out": report(summary="Předáno dál.")},
    }


def brief(client, node_id="focus", **scope):
    return client.get("/api/desktop-v3/node-brief", params={**SCOPE, **scope, "nodeId": node_id})


def save_workspace(client, node_id, sections, expected=0):
    saved = client.post("/api/desktop-v3/agent-workspace", headers=HEADERS, json={
        **SCOPE, "nodeId": node_id, "expectedRevision": expected, "sections": sections, "by": "agent",
    })
    assert saved.status_code == 200, saved.text
    return saved.json()


def test_brief_reads_top_down_from_graph_spec_and_state(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert client.post("/api/node-spec", headers=HEADERS, json={
            **SCOPE, "node": "focus", "expected_revision": 0,
            "fields": {"goal": "Dodat kartu.", "non_goals": "Neřešit frontend.", "acceptance": "Testy zelené."},
        }).status_code == 200
        save_state(client, full_state())

        response = brief(client)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["schema"] == "opora.node-brief/1"
        assert data["node"] == {"id": "focus", "name": "Ohnisko", "kind": "node", "purpose": "Podstata",
                                "path": ["Sektor"], "depth": 1, "sourceRef": None,
                                "type": None, "layer": None, "status": None, "due": None, "model": None, "effort": None,
                                "address": "sektor/ohnisko"}
        assert data["goal"] == {"goal": "Dodat kartu.", "nonGoals": "Neřešit frontend.",
                                "acceptance": "Testy zelené."}
        assert data["definitionOfDone"]["acceptance"] == "Testy zelené."
        assert set(data["definitionOfDone"]) == {"acceptance", "blockConditions"}
        assert data["definitionOfDone"]["blockConditions"] == [
            {"blockId": "b1", "number": "1", "condition": "Testy zelené"}
        ]
        assert data["boundaries"]["nodeRules"][0]["id"] == "nr1"
        assert data["boundaries"]["projectRules"][0]["id"] == "r1"
        assert data["boundaries"]["nonGoals"] == "Neřešit frontend."
        assert data["context"]["materials"] == [
            {"id": "m1", "kind": "link", "path": "https://example.com/spec",
             "caption": "Spec", "url": "https://example.com/spec", "sourceNodeId": "focus"}
        ]
        assert [item["id"] for item in data["context"]["decisions"]] == ["d1"]
        assert set(data["harness"]) == {"actions", "stopConditions"}
        assert data["harness"]["actions"] == [
            {"index": 0, "id": "a1", "pipelineId": "verify.run-tests", "label": "Testy", "params": {}}
        ]
        assert data["outputContract"]["schema"] == "opora.agent-output/1"
        assert set(data["outputContract"]["fields"]) == {"blocks", "reports", "done", "decisions"}


def test_brief_exposes_typed_output_and_exact_request_revision(tmp_path):
    from backend.editor.agent_memory.agent_output import validate_output

    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        saved = save_state(client, full_state())
        contract = brief(client).json()["outputContract"]
        assert contract["request"] == {**SCOPE, "nodeId": "focus", "expectedRevision": saved["revision"],
                                       "contextVersion": brief(client).json()["contextVersion"]}
        schema = contract["jsonSchema"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"schema", "blocks", "reports", "done", "decisions"}
        properties = schema["properties"]
        assert properties["schema"]["const"] == "opora.agent-output/1"
        report = properties["reports"]["items"]
        assert set(report["required"]) == {"edgeId", "log", "summary", "handoff", "improvements", "errors"}
        assert report["properties"]["errors"]["type"] == "string"
        assert report["properties"]["errors"]["maxLength"] == 4000
        assert properties["done"]["properties"]["proposed"]["type"] == "boolean"
        assert contract["transport"]["format"] == "json-object"
        assert contract["transport"]["markdownFences"] is False
        assert contract["reportScope"] == "outgoing-only"
        response = {"schema": properties["schema"]["const"], "blocks": [], "reports": [],
                    "done": {"proposed": False, "note": ""}, "decisions": []}
        validate_output({**contract["request"], "agent": "test", "output": response})


def test_blocks_are_ordered_by_number_and_ports_carry_their_edges(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        save_state(client, full_state())
        data = brief(client).json()
        assert [item["number"] for item in data["blocks"]] == ["1", "2"]
        first = data["blocks"][0]
        assert first["ports"] == [
            {"id": "p1", "label": "Návrh API",
             "edges": [{"edgeId": "e-out", "targetId": "dalsi", "targetName": "Další"}]},
            {"id": "p2", "label": "Oprava", "edges": []},
        ]
        # Blok bez portů (starší zápis) dostane prázdné pole, ne chybu.
        assert data["blocks"][1]["ports"] == []


def test_graph_incoming_outgoing_children_and_reports(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        state = full_state()
        # Zpráva na vazbě, která už v grafu není, zůstává uložená, ale balíček ji nevydá.
        state["edges"]["smazana"] = report(summary="Ze smazané vazby.")
        save_state(client, state)
        data = brief(client).json()
        assert "Ze smazané vazby." not in str(data)
        incoming = data["graph"]["incoming"]
        assert [item["edgeId"] for item in incoming] == ["e-in"]
        assert incoming[0]["from"] == "pred" and incoming[0]["port"] == "next"
        outgoing = data["graph"]["outgoing"]
        assert outgoing[0]["sourceBlockId"] == "b1" and outgoing[0]["sourcePortId"] == "p1"
        assert data["graph"]["children"] == [
            {"id": "dite", "name": "Dítě", "kind": "node", "agentWorkspace": {"frame": "", "handoff": ""}}
        ]
        assert data["context"]["incomingReports"][0]["edgeId"] == "e-in"
        assert data["context"]["incomingReports"][0]["from"] == "pred"
        assert data["context"]["incomingReports"][0]["summary"] == "Router hotový."
        assert data["loop"]["lastReport"]["edgeId"] == "e-out"
        assert data["loop"]["openBlocks"] == 2
        assert data["loop"]["done"] == {"confirmed": False, "at": "", "by": "human", "note": ""}


def test_node_carries_card_fields_and_links_carry_addresses(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        graph = {
            "nodes": [
                {**item, "card": {"layer": "backend", "status": "ready", "due": "2026-10-10", "model": "sonnet", "effort": "high"},
                 "name": "[task] Ohnisko"} if item["id"] == "focus" else item
                for item in GRAPH["nodes"]
            ],
            "edges": GRAPH["edges"],
        }
        view = client.get("/api/view", params=SCOPE).json()
        assert client.post("/api/graph", headers=HEADERS,
                           json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200
        state = full_state()
        state["edges"]["e-out"] = report(sentAt="2026-10-02T08:00:00+00:00", due="2026-10-12")
        save_state(client, state)
        data = brief(client).json()
        node = data["node"]
        assert node["layer"] == "backend"
        assert (node["type"], node["status"], node["due"], node["model"], node["effort"]) == (
            "task", "ready", "2026-10-10", "sonnet", "high")
        assert node["address"] == "sektor/ohnisko" and node["name"] == "[task] Ohnisko"
        incoming, outgoing = data["graph"]["incoming"][0], data["graph"]["outgoing"][0]
        assert incoming["fromAddress"] == "sektor/predchudce" and incoming["toAddress"] == "sektor/ohnisko"
        assert outgoing["toAddress"] == "sektor/dalsi"
        assert outgoing["report"]["sentAt"] == "2026-10-02T08:00:00+00:00"
        assert outgoing["report"]["due"] == "2026-10-12"
        assert "sentAt" not in incoming["report"] and "due" not in incoming["report"]


def test_closed_card_has_done_status(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        state = full_state()
        from backend.editor.agent_memory.test_completion_evidence import evidence
        state["nodes"]["focus"]["evidence"] = evidence()
        state["nodes"]["focus"]["done"] = {"confirmed": True, "at": "2026-09-14T09:00:00+00:00",
                                           "by": "human", "note": ""}
        save_state(client, state)
        assert brief(client).json()["node"]["status"] == "done"


def test_stop_conditions_name_condition_missing_material_must_not_and_closed_card(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        state = full_state()
        from backend.editor.agent_memory.test_completion_evidence import evidence
        state["nodes"]["focus"]["evidence"] = evidence()
        state["nodes"]["focus"]["done"] = {"confirmed": True, "at": "2026-09-14T09:00:00+00:00",
                                           "by": "human", "note": "Hotovo."}
        save_state(client, state)
        stops = brief(client).json()["harness"]["stopConditions"]
        assert any("Testy zelené" in text for text in stops)
        assert any("Nesahat na frontend." in text for text in stops)
        assert any("Nikdy nespouštět model." in text for text in stops)
        assert any("uzavřená" in text for text in stops)
        # Podklad tu je, takže chybějící podklad se neuvádí.
        assert not any("nemá žádný podklad" in text for text in stops)


def test_card_without_state_or_materials_still_builds_with_defaults(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        data = brief(client, "dalsi").json()
        assert data["blocks"] == [] and data["context"]["materials"] == []
        assert data["goal"] == {"goal": "", "nonGoals": "", "acceptance": ""}
        assert "phase" not in data["harness"]
        assert data["loop"]["lastReport"] is None and data["loop"]["done"]["confirmed"] is False
        assert not any("nemá žádný podklad" in text for text in data["harness"]["stopConditions"])
        assert any(item["id"] == "materials" for item in data["orientation"]["optionalContext"])
        assert data["node"]["path"] == ["Sektor"] and data["node"]["depth"] == 0


@pytest.mark.parametrize("node_id", ["nikdo", "ne platné!", ""])
def test_unknown_or_invalid_node_is_rejected_with_409(tmp_path, node_id):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert brief(client, node_id).status_code == 409


def test_context_comments_and_inner_comments_are_ordered_by_position(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        graph = {
            "nodes": [
                *GRAPH["nodes"],
                # Stejná vrstva jako "focus" (parentId "sektor"); pořadí je podle y, pak x.
                {"id": "note-far", "parentId": "sektor", "kind": "comment", "name": "Pozdější",
                 "purpose": "Napsáno později.", "x": 300, "y": 100},
                {"id": "note-near", "parentId": "sektor", "kind": "comment", "name": "Bližší",
                 "purpose": "Napsáno dřív.", "x": 0, "y": 50},
                # Vrstva uvnitř "focus" (parentId "focus").
                {"id": "note-inner", "parentId": "focus", "kind": "comment", "name": "Vnitřní",
                 "purpose": "Uvnitř karty.", "x": 0, "y": 0},
            ],
            "edges": GRAPH["edges"],
        }
        view = client.get("/api/view", params=SCOPE).json()
        saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        data = brief(client).json()
        assert data["context"]["comments"] == [
            {"id": "note-near", "title": "Bližší", "text": "Napsáno dřív."},
            {"id": "note-far", "title": "Pozdější", "text": "Napsáno později."},
        ]
        assert data["graph"]["innerComments"] == [
            {"id": "note-inner", "title": "Vnitřní", "text": "Uvnitř karty."},
        ]


def test_context_area_and_graph_area_flows_and_members(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        graph = {
            "nodes": [
                *GRAPH["nodes"],
                # Oblast na stejné vrstvě jako "focus" (parentId "sektor"); její obdélník
                # [-50, 350] x [-50, 350] obsahuje střed "focus" (180, 120), ale ne "pred"
                # (-164, 120) ani "dalsi" (436, 120).
                {"id": "region-1", "parentId": "sektor", "kind": "area", "name": "Oblast",
                 "purpose": "Jádro řešení.", "x": -50, "y": -50, "size": {"w": 400, "h": 400}},
                # Další karta na stejné vrstvě, jejíž střed (236, 220) je taky uvnitř region-1.
                {"id": "friend", "parentId": "sektor", "kind": "node", "name": "Kámoš",
                 "purpose": "", "x": 100, "y": 100},
                # Komentář uvnitř region-1: patří geometricky, ale v areaMembers se nesmí objevit.
                {"id": "region-note", "parentId": "sektor", "kind": "comment", "name": "Poznámka",
                 "purpose": "", "x": 100, "y": 100},
                {"id": "region-2", "parentId": "sektor", "kind": "area", "name": "Cíl toku",
                 "purpose": "", "x": 2000, "y": 2000, "size": {"w": 200, "h": 200}},
                {"id": "region-3", "parentId": "sektor", "kind": "area", "name": "Zdroj toku",
                 "purpose": "", "x": -2000, "y": -2000, "size": {"w": 200, "h": 200}},
            ],
            "edges": [
                *GRAPH["edges"],
                {"id": "flow-out", "source": "region-1", "target": "region-2", "port": "flow"},
                {"id": "flow-in", "source": "region-3", "target": "region-1", "port": "flow"},
            ],
        }
        view = client.get("/api/view", params=SCOPE).json()
        saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        # Soused v oblasti nese jen rámec a předávku; ostatní sekce si agent dočte odkazem.
        save_workspace(client, "friend", {"frame": "Rámec kámoše", "log": "Skrytý postup kámoše",
                                          "handoff": "Předávka kámoše"})
        data = brief(client).json()
        assert data["context"]["area"] == {"id": "region-1", "name": "Oblast", "purpose": "Jádro řešení."}
        assert sorted(data["graph"]["areaFlows"], key=lambda item: item["edgeId"]) == [
            {"edgeId": "flow-in", "from": "region-3", "fromName": "Zdroj toku",
             "to": "region-1", "toName": "Oblast", "direction": "in"},
            {"edgeId": "flow-out", "from": "region-1", "fromName": "Oblast",
             "to": "region-2", "toName": "Cíl toku", "direction": "out"},
        ]
        assert data["graph"]["areaMembers"] == [
            {"id": "friend", "name": "Kámoš", "kind": "node",
             "agentWorkspace": {"frame": "Rámec kámoše", "handoff": "Předávka kámoše"}}
        ]
        assert "Skrytý postup kámoše" not in str(data)

        # Karta mimo žádnou oblast (např. "pred") nemá area a nemá tok ani sousedy.
        outside = brief(client, "pred").json()
        assert outside["context"]["area"] is None
        assert outside["graph"]["areaFlows"] == []
        assert outside["graph"]["areaMembers"] == []


def test_agent_workspace_travels_with_the_card_its_links_and_its_lineage(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        save_workspace(client, "focus", {
            "frame": "Rámec ohniska", "log": "Postup ohniska", "failures": "Co selhalo",
            "fixes": "Co se spravilo", "handoff": "Předávka ohniska",
        })
        save_workspace(client, "pred", {"handoff": "Od předchůdce"})
        save_workspace(client, "dalsi", {"frame": "Rámec dalšího"})
        save_workspace(client, "dite", {"frame": "Rámec dítěte", "log": "Skrytý postup dítěte",
                                        "handoff": "Předávka dítěte"})
        save_workspace(client, "sektor", {"frame": "Rámec sektoru", "failures": "Skryté chyby sektoru",
                                          "handoff": "Předávka sektoru"})
        data = brief(client).json()

        own = data["agentWorkspace"]
        assert set(own) == {"frame", "log", "failures", "fixes", "handoff", "updatedAt", "by"}
        assert own["frame"] == "Rámec ohniska" and own["log"] == "Postup ohniska"
        assert own["failures"] == "Co selhalo" and own["fixes"] == "Co se spravilo"
        assert own["handoff"] == "Předávka ohniska" and own["by"] == "agent" and own["updatedAt"]

        # Vazba nese celý prostor karty na druhé straně, příchozí i odchozí.
        incoming = data["graph"]["incoming"][0]["agentWorkspace"]
        assert set(incoming) == set(own) and incoming["handoff"] == "Od předchůdce"
        assert data["graph"]["outgoing"][0]["agentWorkspace"]["frame"] == "Rámec dalšího"

        # Potomek a rodič nesou jen rámec a předávku; zbytek si agent dočte odkazem.
        assert data["graph"]["children"] == [
            {"id": "dite", "name": "Dítě", "kind": "node",
             "agentWorkspace": {"frame": "Rámec dítěte", "handoff": "Předávka dítěte"}}
        ]
        assert data["graph"]["parent"] == {
            "id": "sektor", "name": "Sektor", "kind": "sector",
            "goal": {"goal": "", "nonGoals": "", "acceptance": ""}, "rules": [],
            "agentWorkspace": {"frame": "Rámec sektoru", "handoff": "Předávka sektoru"},
        }
        assert "Skrytý postup dítěte" not in str(data)
        assert "Skryté chyby sektoru" not in str(data)


def test_card_without_workspace_is_empty_and_root_card_has_no_parent(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        data = brief(client, "dalsi").json()
        assert data["agentWorkspace"] == {"frame": "", "log": "", "failures": "", "fixes": "",
                                          "handoff": "", "updatedAt": "", "by": "human"}
        assert data["graph"]["parent"] == {
            "id": "sektor", "name": "Sektor", "kind": "sector",
            "goal": {"goal": "", "nonGoals": "", "acceptance": ""}, "rules": [],
            "agentWorkspace": {"frame": "", "handoff": ""},
        }
        assert data["graph"]["children"] == []
        # Kořenová karta rodiče nemá.
        assert brief(client, "sektor").json()["graph"]["parent"] is None


def test_knowledge_graph_is_available_only_with_both_graphify_files(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        seed_graph(client)
        # Projekt bez připojeného zdroje mapu nemá; cesty zůstávají referencí.
        assert brief(client).json()["context"]["knowledgeGraph"] == {
            "available": False, "report": "graphify-out/GRAPH_REPORT.md", "graph": "graphify-out/graph.json",
        }
        source = tmp_path / "source"
        output = source / "graphify-out"
        output.mkdir(parents=True)
        app.state.service.project_hub.settings = lambda project: {"project": {"sourcePath": str(source)}}
        (output / "graph.json").write_text("{}", encoding="utf-8")
        # Jeden ze dvou souborů není mapa.
        assert brief(client).json()["context"]["knowledgeGraph"]["available"] is False
        (output / "GRAPH_REPORT.md").write_text("# mapa", encoding="utf-8")
        assert brief(client).json()["context"]["knowledgeGraph"] == {
            "available": True, "report": "graphify-out/GRAPH_REPORT.md", "graph": "graphify-out/graph.json",
        }


def test_graph_parent_carries_its_own_goal_and_rules_for_the_child(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert client.post("/api/node-spec", headers=HEADERS, json={
            **SCOPE, "node": "focus", "expected_revision": 0,
            "fields": {"goal": "Dodat kartu.", "non_goals": "Neřešit frontend.", "acceptance": "Testy zelené."},
        }).status_code == 200
        save_state(client, full_state())

        # "dite" je dítě "focus": rodič v jejím balíčku nese cíl a pravidla "focus".
        data = brief(client, "dite").json()
        assert data["graph"]["parent"]["id"] == "focus"
        assert data["graph"]["parent"]["goal"] == {
            "goal": "Dodat kartu.", "nonGoals": "Neřešit frontend.", "acceptance": "Testy zelené.",
        }
        assert data["graph"]["parent"]["rules"] == [
            {"id": "nr1", "text": "Nesahat na frontend.", "kind": "must_not"}
        ]

        # Rodič bez uloženého zadání a bez pravidel uzlu dostane prázdné hodnoty, ne chybu.
        root_child = brief(client, "focus").json()
        assert root_child["graph"]["parent"]["id"] == "sektor"
        assert root_child["graph"]["parent"]["goal"] == {"goal": "", "nonGoals": "", "acceptance": ""}
        assert root_child["graph"]["parent"]["rules"] == []


def test_optional_material_context_inherits_ancestors_without_blocking_empty_tasks(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        state = full_state()
        # "focus" nemá vlastní podklad, ale jeho rodič "sektor" ano.
        state["nodes"]["focus"]["materials"] = []
        state["nodes"]["sektor"] = {
            "phase": "discover", "criteria": [], "steps": [],
            "materials": [{"id": "m-sektor", "kind": "link", "path": "https://example.com/sektor",
                           "caption": "Sektor"}],
        }
        save_state(client, state)
        inherited = brief(client).json()
        assert not any("nemá žádný podklad" in text for text in inherited["harness"]["stopConditions"])
        assert inherited["context"]["materials"][0]["sourceNodeId"] == "sektor"
        assert not any(item["id"] == "materials" for item in inherited["orientation"]["optionalContext"])

        # Bez podkladu karty i předků jde o volitelný kontext, nikoli důvod zastavit práci.
        state["nodes"]["sektor"]["materials"] = []
        save_state(client, state, expected=1)
        empty = brief(client).json()
        assert not any("nemá žádný podklad" in text for text in empty["harness"]["stopConditions"])
        assert empty["context"]["materials"] == []
        assert any(item["id"] == "materials" for item in empty["orientation"]["optionalContext"])


def test_upload_material_gets_the_servable_file_url(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        state = full_state()
        state["nodes"]["focus"]["materials"] = [
            {"id": "m-upload", "kind": "upload", "path": "20260101-120000-abcdef01.png", "caption": "Screenshot"},
            {"id": "m-link", "kind": "link", "path": "https://example.com/spec", "caption": "Spec"},
            {"id": "m-source", "kind": "source", "path": "README.md", "caption": "Readme"},
        ]
        save_state(client, state)
        materials = {item["id"]: item for item in brief(client).json()["context"]["materials"]}
        assert materials["m-upload"]["url"] == (
            "/api/node-materials/file?project=draft&nodeId=focus&file=20260101-120000-abcdef01.png"
        )
        assert materials["m-link"]["url"] == "https://example.com/spec"
        assert materials["m-source"]["url"] == ""


def test_brief_appends_orientation_and_actual_paginated_communication_with_receipt(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        # Přes první stránku: brief nesmí zploštit kurzor ani zahodit poslední záznam s receipt.
        for index in range(30):
            old = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json={
                **SCOPE, "sourceNodeId": "pred", "targetNodeId": "focus", "kind": "handoff",
                "body": f"Starší {index}", "replyToMessageId": None,
                "idempotencyKey": f"orientation-old-{index}", "senderLabel": "předchozí agent",
            })
            assert old.status_code == 200, old.text
        created = client.post("/api/desktop-v3/agent-messages", headers=HEADERS, json={
            **SCOPE, "sourceNodeId": "pred", "targetNodeId": "focus", "kind": "handoff",
            "body": "Přečti skutečný brief.", "replyToMessageId": None,
            "idempotencyKey": "orientation-brief-message", "senderLabel": "předchozí agent",
        })
        assert created.status_code == 200, created.text
        message = created.json()["message"]
        received = client.post("/api/desktop-v3/agent-message-receipt", headers=HEADERS, json={
            **SCOPE, "nodeId": "focus", "messageId": message["id"], "digest": message["digest"],
            "disposition": "accepted", "note": "Přečteno.", "recipientLabel": "nový agent",
        })
        assert received.status_code == 200, received.text

        data = brief(client).json()
        assert data["orientation"]["schema"] == "opora.agent-orientation/1"
        assert data["orientation"]["scope"]["nodeId"] == "focus"
        incoming = data["communication"]["incoming"]
        assert len(incoming["messages"]) == 30 and incoming["hasMore"] is True and incoming["nextBefore"] is not None
        assert incoming["messages"][0] == {**message, "identityVerified": False, "receipt": {
            "disposition": "accepted", "note": "Přečteno.", "recipientLabel": "nový agent",
            "identityVerified": False, "createdAt": received.json()["message"]["receipt"]["createdAt"],
        }}
        assert data["communication"]["outgoing"] == {"messages": [], "hasMore": False, "nextBefore": None}
        assert data["communication"]["endpoints"] == {
            "list": "/api/desktop-v3/agent-messages", "send": "/api/desktop-v3/agent-messages",
            "receipt": "/api/desktop-v3/agent-message-receipt",
        }


# ---- paměť role u karty (OpenViking) ----------------------------------------------


def test_card_without_a_role_reports_skipped_role_memory(tmp_path):
    """Karta bez role není prázdná paměť; balíček to řekne rovnou."""
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        save_state(client, full_state())
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"}).json()
        assert brief["context"]["roleMemory"] == {
            "status": "skipped", "reason": "karta nemá roli", "role": None, "items": [],
        }
        assert not any(item["id"] == "role-memory" for item in brief["orientation"]["readingOrder"])


def test_role_memory_is_recalled_for_a_card_with_a_role():
    from backend.editor.agent_packet.node_brief import role_memory

    class FakeMemory:
        def __init__(self, result):
            self.result = result
            self.calls = []

        def recall(self, role, project, node_id, query, max_tokens=600):
            self.calls.append((role, project, node_id, query))
            return self.result

    memory = FakeMemory({
        "status": "configured", "role": "role-backend", "rendered": "...", "truncated": False,
        "items": [{"uri": "viking://user/role-backend/memories/a.md", "text": "Router do api.",
                   "score": 0.9, "origin": "self"}],
    })
    found = role_memory(memory, {"agentRole": "role-backend"}, "draft", "focus", "Dodat router")
    assert found["status"] == "configured" and found["role"] == "role-backend"
    assert found["items"][0]["origin"] == "self"
    assert memory.calls == [("role-backend", "draft", "focus", "Dodat router")]


def test_role_memory_never_breaks_the_brief_when_the_server_is_down():
    from backend.editor.agent_packet.node_brief import role_memory

    class BrokenMemory:
        def recall(self, *args, **kwargs):
            raise OSError("OpenViking není dostupný.")

    found = role_memory(BrokenMemory(), {"agentRole": "role-db"}, "draft", "focus", "cíl")
    assert found == {"status": "unavailable", "reason": "Paměť rolí neodpověděla.",
                     "role": "role-db", "items": []}
    missing = role_memory(None, {"agentRole": "role-db"}, "draft", "focus", "cíl")
    assert missing["status"] == "unavailable" and missing["items"] == []


def test_project_memory_rules_stay_untouched_by_role_memory(tmp_path):
    """`context.memory.rules` čte předání externímu agentovi; paměť role do něj nesahá."""
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        save_state(client, full_state())
        response = client.post("/api/desktop-v3/packet/preview", headers=HEADERS, json={
            **SCOPE, "nodeId": "focus", "path": "", "sessionId": "", "references": [], "note": "",
        })
        assert response.status_code == 200, response.text
        packet = response.json()["packet"]
        assert packet["context"]["memory"]["rules"][0]["text"] == "Nikdy nespouštět model."
        assert "roleMemory" not in packet["context"]["memory"]


def test_brief_carries_card_text_as_content_or_null(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert brief(client).json()["content"] is None
        excerpt = "Zadání Jihlava, kap. Zpracování dat:\n1. Nahrání | 2. OCR > 3. Chunking"
        saved = client.post("/api/node-text", headers=HEADERS,
                            json={**SCOPE, "node": "focus", "expected_revision": 0, "text": excerpt})
        assert saved.status_code == 200, saved.text
        assert brief(client).json()["content"] == {"text": excerpt, "revision": 1}
        # Text se v balíčku rediguje stejně jako zbytek; prázdný text je zase null.
        client.post("/api/node-text", headers=HEADERS,
                    json={**SCOPE, "node": "focus", "expected_revision": 1, "text": "token: abcdefgh12345678"})
        assert "abcdefgh12345678" not in brief(client).json()["content"]["text"]
        client.post("/api/node-text", headers=HEADERS,
                    json={**SCOPE, "node": "focus", "expected_revision": 2, "text": "  "})
        assert brief(client).json()["content"] is None


def test_storyboard_section_only_for_cards_with_a_storyboard(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed_graph(client)
        assert "storyboard" not in brief(client).json()
        board = {"animation": "kulicka", "duration": 10, "moments": [
            {"t": 1, "comment": "Plošší.", "annotations": [{"kind": "note", "at": {"x": 0.5, "y": 0.8}, "text": "stín"}]}]}
        saved = client.post("/api/storyboard", headers=HEADERS, json={
            **SCOPE, "nodeId": "focus", "expected_revision": 0, "storyboard": board})
        assert saved.status_code == 200, saved.text
        result = brief(client).json()
        moment = result["storyboard"]["moments"][0]
        assert moment["comment"] == "Plošší." and moment["annotationsText"] == ["poznámka u (0.50, 0.80): stín"]
        assert "storyboard.moments[].comment" in result["trust"]["instructions"]
        assert "storyboard" not in brief(client, "dalsi").json()
