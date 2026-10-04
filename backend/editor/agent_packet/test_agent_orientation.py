"""Autoritativní orientace odvozená pouze z node-briefu, bez zápisu nebo čtení souborů."""
from backend.editor.agent_packet.agent_orientation import orientation_from_brief


def test_orientation_keeps_actual_ids_empty_blocks_and_marks_context_gaps():
    brief = {
        "node": {"id": "focus", "name": "Ohnisko", "kind": "node", "purpose": "Dodat UI", "path": ["Sektor"]},
        "readOnly": True,
        "goal": {"goal": "", "nonGoals": "Nezasahovat mimo kartu", "acceptance": ""},
        "definitionOfDone": {"criteria": [], "blockConditions": []},
        "boundaries": {"nodeRules": [], "projectRules": [], "nonGoals": "Nezasahovat mimo kartu"},
        "context": {"materials": [{"id": "m1", "kind": "link", "path": "https://example.test/spec", "caption": "Spec", "url": "https://example.test/spec", "sourceNodeId": "sektor"}], "knowledgeGraph": {"available": False, "report": "graphify-out/GRAPH_REPORT.md", "graph": "graphify-out/graph.json"}},
        "harness": {"steps": [{"id": "s1", "text": "Přečíst spec", "done": False}], "stopConditions": ["Chybí podklad."]},
        "blocks": [],
        "graph": {"incoming": [], "outgoing": []},
        "agentWorkspace": {"frame": "", "log": "", "failures": "", "fixes": "", "handoff": ""},
    }

    orientation = orientation_from_brief(brief, "draft", "draft")

    assert orientation["schema"] == "opora.agent-orientation/1"
    assert orientation["scope"] == {"project": "draft", "workspace": "draft", "nodeId": "focus", "path": ["Sektor", "Ohnisko"], "readOnly": True}
    assert orientation["goal"]["status"] == "missing"
    assert orientation["materials"] == [{
        "id": "m1", "sourceNodeId": "sektor", "kind": "link", "path": "https://example.test/spec",
        "caption": "Spec", "url": "https://example.test/spec", "status": "present",
    }]
    assert orientation["blocks"] == []
    assert {item["id"] for item in orientation["contextGaps"]} == {"goal", "acceptance"}
    assert {item["id"] for item in orientation["optionalContext"]} == {"knowledge-graph"}
    assert all(item["sources"] for item in orientation["contextGaps"])
    assert orientation["readingOrder"][0]["source"] == "node"
    workspace = next(item for item in orientation["readingOrder"] if item["id"] == "workspace")
    assert workspace["status"] == "unavailable"
    assert workspace["reason"] == "Pracovní paměť se v tomto pohledu pouze ke čtení nezobrazuje."
    assert orientation["nextAction"]["kind"] == "read-only"
    assert orientation["nextAction"]["sources"] == [{"source": "loop.done"}]
    assert orientation["safety"] == {"readOnly": True, "automaticModelInvocation": False, "automaticAck": False, "ownershipTransfer": False}


def test_orientation_keeps_blank_workspace_missing_for_editable_confirmed_brief():
    brief = {
        "node": {"id": "focus", "name": "Ohnisko", "kind": "node", "purpose": "Dodat UI", "path": []},
        "readOnly": False,
        "goal": {"goal": "Dodat UI", "nonGoals": "", "acceptance": "Funguje."},
        "definitionOfDone": {"criteria": [], "blockConditions": []},
        "boundaries": {"nodeRules": [], "projectRules": [], "nonGoals": ""},
        "context": {"materials": [], "knowledgeGraph": {"available": True}},
        "harness": {"steps": [], "stopConditions": []}, "blocks": [], "graph": {"incoming": [], "outgoing": []},
        "loop": {"done": {"confirmed": True}},
        "agentWorkspace": {"frame": "", "log": "", "failures": "", "fixes": "", "handoff": ""},
    }

    orientation = orientation_from_brief(brief)

    workspace = next(item for item in orientation["readingOrder"] if item["id"] == "workspace")
    assert workspace["status"] == "missing"
    assert "reason" not in workspace
    assert {item["id"] for item in orientation["contextGaps"]} == {"agent-workspace"}
    assert orientation["nextAction"]["kind"] == "read-only"
    assert orientation["scope"]["readOnly"] is True
    assert orientation["safety"]["readOnly"] is True


def _brief_with_role_memory(role_memory):
    return {
        "node": {"id": "focus", "name": "Ohnisko", "kind": "node", "purpose": "", "path": []},
        "readOnly": False,
        "goal": {"goal": "Dodat router", "nonGoals": "", "acceptance": "Testy zelené"},
        "definitionOfDone": {"criteria": [], "blockConditions": []},
        "boundaries": {"nodeRules": [], "projectRules": [], "nonGoals": ""},
        "context": {"materials": [], "knowledgeGraph": {"available": True, "report": "r", "graph": "g"},
                    "roleMemory": role_memory},
        "harness": {"steps": [], "stopConditions": []},
        "blocks": [],
        "graph": {"incoming": [], "outgoing": []},
        "agentWorkspace": {"frame": "Rámec", "log": "", "failures": "", "fixes": "", "handoff": ""},
        "loop": {"done": {"confirmed": False}},
    }


def test_role_memory_enters_the_reading_order_only_when_it_carries_something():
    filled = orientation_from_brief(_brief_with_role_memory({
        "status": "configured", "role": "role-backend",
        "items": [{"uri": "viking://user/role-backend/memories/a.md", "text": "Router patří do api.",
                   "score": 0.9, "origin": "self"}],
    }), "draft", "draft")
    item = next(entry for entry in filled["readingOrder"] if entry["id"] == "role-memory")
    assert item["label"] == "Paměť role" and item["source"] == "context.roleMemory"
    assert item["status"] == "present" and item["role"] == "role-backend"


def test_empty_skipped_or_unavailable_role_memory_is_not_offered_as_reading():
    for role_memory in (
        {"status": "configured", "role": "role-backend", "items": []},
        {"status": "skipped", "reason": "karta nemá roli", "role": None, "items": []},
        {"status": "unavailable", "reason": "OpenViking není dostupný.", "role": "role-db", "items": []},
        {"status": "disabled", "reason": "vypnuto", "role": "role-db", "items": []},
    ):
        orientation = orientation_from_brief(_brief_with_role_memory(role_memory), "draft", "draft")
        assert not any(entry["id"] == "role-memory" for entry in orientation["readingOrder"])


def test_orientation_survives_an_older_brief_without_role_memory():
    brief = _brief_with_role_memory({})
    del brief["context"]["roleMemory"]
    orientation = orientation_from_brief(brief, "draft", "draft")
    assert not any(entry["id"] == "role-memory" for entry in orientation["readingOrder"])


def test_new_work_does_not_require_a_previous_agents_handoff():
    brief = _brief_with_role_memory({})
    brief["agentWorkspace"]["frame"] = ""
    orientation = orientation_from_brief(brief, "draft", "draft")
    assert orientation["contextGaps"] == []
    assert orientation["nextAction"]["kind"] == "follow-harness"
    assert any(item["id"] == "materials" for item in orientation["optionalContext"])


def test_continuing_previous_work_still_identifies_a_missing_handoff():
    brief = _brief_with_role_memory({})
    brief["agentWorkspace"]["frame"] = ""
    brief["resultHistory"] = {"items": [{"id": "previous-result"}]}
    orientation = orientation_from_brief(brief, "draft", "draft")
    assert {item["id"] for item in orientation["contextGaps"]} == {"agent-workspace"}
