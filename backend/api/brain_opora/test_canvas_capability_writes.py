"""Named writes persist reviewed proposals without editing accepted live content."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import accept
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def test_content_adapters_replay_and_keep_live_documents_unchanged(setup):
    client, service, auth = setup
    context = call(client, auth, "opora_graph_routes.context").json()["result"]
    base = {"parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"], "subject": "Seed"}
    seed = call(client, auth, "opora_graph_routes.create", {**base, "plan": {
        "nodes": [{"ref": "task", "kind": "node", "name": "Task"}]}}, "seed")
    assert seed.status_code == 200, seed.text
    item = seed.json()["result"]
    node = item["refs"]["task"]
    # Human acceptance exists only in this isolated fixture; adapters never do it.
    accept(OporaGraphProposals(service), item)
    context = call(client, auth, "opora_graph_routes.context").json()["result"]
    base.update(parentRevision=context["acceptedHead"], expectedGraphDigest=context["graphDigest"])
    state = DesktopV3State(service).current("draft", "draft")["revision"]
    for name, key, value, store in (("save_node_text", "text", "Pending full text", service.texts),
                                   ("save_node_spec", "fields", {"goal": "Pending goal"}, service.specs)):
        before = store.read(("draft", "draft", node))
        data = {**base, "node": node, "expectedStateRevision": state,
                "expectedRevision": before["revision"], key: value}
        response = call(client, auth, "node_routes." + name, data, name)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["verified"] and not result["accepted"]
        assert result["result"]["schemaVersion"] == 3
        assert call(client, auth, "node_routes." + name, data, name).json() == result
        assert store.read(("draft", "draft", node)) == before
        assert OporaGraphProposals(service).context(**SCOPE)["acceptedHead"] == context["acceptedHead"]
        assert call(client, auth, "node_routes." + name, {**data, "expectedRevision": 99}, name + "-stale").status_code in (409, 422)
        assert call(client, auth, "node_routes." + name, {**data, "subject": "Different"}, name).status_code == 409


def test_initial_canvas_plan_preserves_full_native_draft_and_replay(setup):
    client, service, auth = setup
    context = OporaGraphProposals(service).context(**SCOPE)
    data = {"parentRevision": None, "expectedGraphDigest": context["graphDigest"], "subject": "Initial draft",
            "plan": {"nodes": [{"ref": "first", "kind": "node", "name": "First", "text": "Full initial content",
                                "spec": {"goal": "Initial goal"}}]}}
    response = call(client, auth, "canvas_routes.canvas_plan", data, "initial")
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["kind"] == "working-draft" and saved["verified"] and not saved["accepted"]
    node = saved["result"]["refs"]["first"]
    assert service.texts.read(("draft", "draft", node))["text"] == "Full initial content"
    assert service.specs.read(("draft", "draft", node))["fields"]["goal"] == "Initial goal"
    assert call(client, auth, "canvas_routes.canvas_plan", data, "initial").json() == saved
    assert OporaGraphProposals(service).context(**SCOPE)["acceptedHead"] is None
    changed = {**data, "plan": {"nodes": [{"ref": "first", "kind": "node", "name": "Different"}]}}
    assert call(client, auth, "canvas_routes.canvas_plan", changed, "initial").status_code == 409
