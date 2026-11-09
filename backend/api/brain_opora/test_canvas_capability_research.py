"""Research adapter preserves native CAS, immutable evidence and explicit review authorship."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.api.editor.test_research_routes import card, edge
from backend.editor.research import decisions, decision_tasks
from backend.editor.research.test_decision_tasks import setup as seed_review, TASKS


def test_native_atomic_research_batch_replay_and_full_revision_readback(setup):
    client, service, auth = setup
    operations = [card(content="Full evidence" * 1000), card("rc_logic"), edge()]
    first = call(client, auth, "research_routes.apply", {"operations": operations}, "native-batch")
    assert first.status_code == 200 and first.json()["verified"], first.text
    assert call(client, auth, "research_routes.apply", {"operations": operations}, "native-batch").json() == first.json()
    assert call(client, auth, "research_routes.apply", {"operations": [card(title="Different")]}, "native-batch").status_code == 409
    assert call(client, auth, "research_routes.apply", {"operations": [card()]}, "stale").status_code == 409
    detail = client.get("/api/research/cards/rc_login", params={**SCOPE, "revision": 1}, headers=auth).json()
    assert detail["card"] == first.json()["result"]["cards"][0]
    bad = call(client, auth, "research_routes.apply", {"operations": [card("rc_atomic"), edge(id="bad", toId="missing")]}, "bad")
    assert bad.status_code == 409
    assert client.get("/api/research/cards/rc_atomic", params=SCOPE, headers=auth).status_code == 404


def test_native_review_reads_do_not_create_approval_or_tasks(setup):
    client, service, auth = setup
    from backend.canvas.canvas_plan import apply_plan
    apply_plan(service, {**SCOPE, "digest": service.view("draft", "draft")["digest"],
        "plan": {"nodes": [{"ref": "seed", "kind": "node", "name": "Seed"}]}})
    payload = seed_review(service)
    review = decisions.review(service, "draft", "draft", payload, "human")  # explicit isolated human fixture
    receipt = decision_tasks.materialize(service, "draft", "draft", review["id"], TASKS, {"kind": "agent", "name": "heart"})
    for capability, data, path, extra in (
        ("listing", {"decisionId": "rc_decision"}, "/api/research/decision-reviews", {"decisionId": "rc_decision"}),
        ("read", {"id": review["id"]}, "/api/research/decision-reviews/" + review["id"], {}),
        ("task_status", {"id": review["id"]}, "/api/research/decision-reviews/" + review["id"] + "/tasks", {}),
    ):
        actual = call(client, auth, "research_decision_routes." + capability, data)
        native = client.get(path, params={**SCOPE, **extra}, headers=auth)
        assert actual.status_code == native.status_code == 200
        assert actual.json()["result"] == native.json()
    assert not decision_tasks.status(service, "draft", "draft", review["id"])["accepted"]
    assert decisions.read(service, "draft", "draft", review["id"])["by"] == "human"
