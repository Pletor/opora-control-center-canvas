"""Real Heart middleware delegates canonical sources and accepted Storyboards."""
import pytest
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import proposal, accept
from backend.editor.storyboard.test_storyboard import board
from backend.brain_opora.determinism import tokens


def node(service):
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    return item["refs"]["new"]


def save(client, auth, target, revision=0, title="Contract", key="scene"):
    return call(client, auth, "storyboard_routes.storyboard_write",
        {"nodeId": target, "expected_revision": revision, "storyboard": board(title=title)}, key)


def content(client, auth, target, value, key="proposal"):
    head = call(client, auth, "opora_content_routes.listing").json()["result"]["acceptedHead"]
    return call(client, auth, "opora_content_routes.create", {"expectedAcceptedHead": head,
        "subject": "Scene approval", "changes": [{"kind": "storyboard", "target": target,
            "field": "storyboard", "value": value}]}, key)


def approval(item):
    return {"identifier": item["id"], "expectedAcceptedHead": item["parentRevision"],
        "reviewedProposalId": item["id"], "adoptBaseContentDigest": item["baseContentDigest"]
        if item["requiresBaseContentAdoption"] else None}


def test_storyboard_history_replay_and_native_accepted_manifest(setup):
    client, service, auth = setup
    target = node(service)
    first = save(client, auth, target)
    assert first.status_code == 200, first.text
    assert save(client, auth, target).json() == first.json()
    assert save(client, auth, target, title="Mismatch").status_code == 409
    assert save(client, auth, target, key="stale").status_code == 409
    scene = call(client, auth, "storyboard_routes.storyboard_read", {"nodeId": target}).json()["result"]["storyboard"]
    created = content(client, auth, target, scene)
    assert created.status_code == 200, created.text
    item = created.json()["result"]
    assert content(client, auth, target, scene).json() == created.json()
    review = call(client, auth, "opora_content_routes.detail", {"identifier": item["id"]})
    assert review.json()["result"]["proposal"] == item
    accepted = call(client, auth, "opora_content_routes.accept", approval(item), "accept")
    assert accepted.status_code == 409  # Token alone never grants native acceptance authority.
    service.project_hub.set_agent_autonomy({"project": "draft", "full": True})
    accepted = call(client, auth, "opora_content_routes.accept", approval(item), "accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["result"]["contentManifestId"]
    assert call(client, auth, "opora_content_routes.accept", approval(item), "accept").json() == accepted.json()
    assert save(client, auth, target, 2, "New draft", "new").status_code == 200
    historical = call(client, auth, "storyboard_routes.storyboard_read", {"nodeId": target, "revision": 1})
    assert historical.status_code == 200 and historical.json()["result"]["storyboard"] == scene


def test_content_stale_and_native_sql_failure_rollback(setup, monkeypatch):
    from database.repositories.opora_content_records import ContentRecords
    from backend.editor.storyboard.storyboard import StoryboardService
    client, service, auth = setup
    target = node(service)
    service.project_hub.set_agent_autonomy({"project": "draft", "full": True})
    assert save(client, auth, target).status_code == 200
    saved = StoryboardService(service).read("draft", "draft", target)
    item = content(client, auth, target, board(title="After acceptance")).json()["result"]
    original = ContentRecords.insert
    def fail(self, value, *, manifest=False):
        if manifest:
            raise ValueError("Forced manifest rollback")
        return original(self, value, manifest=manifest)
    monkeypatch.setattr(ContentRecords, "insert", fail)
    refused = call(client, auth, "opora_content_routes.accept", approval(item), "rollback")
    assert refused.status_code == 409, refused.text
    assert StoryboardService(service).read("draft", "draft", target) == saved
    assert call(client, auth, "opora_content_routes.detail", {"identifier": item["id"]}).json()["result"]["accepted"] is None
    monkeypatch.setattr(ContentRecords, "insert", original)
    assert save(client, auth, target, 1, "Changed", "changed").status_code == 200
    assert call(client, auth, "opora_content_routes.accept", approval(item), "stale-accept").status_code == 409


def test_scoped_knowledge_no_foreign_reads_and_workers_denied(setup, monkeypatch):
    from backend.editor.research import knowledge
    client, service, auth = setup
    context = call(client, auth, "research_knowledge_routes.context")
    assert context.status_code == 200, context.text
    search = call(client, auth, "research_knowledge_routes.search", {"scopes": [SCOPE], "query": "evidence"})
    assert search.status_code == 200, search.text
    touched = []
    monkeypatch.setattr(knowledge.research, "detail", lambda *args: touched.append(args))
    foreign = {"projectId": "foreign", "workspaceId": "draft", "id": "source", "revision": 1}
    refused = call(client, auth, "research_knowledge_routes.bind", {"scopeNodeId": "", "source": foreign,
        "expectedRevision": 0, "archived": False}, "foreign")
    assert refused.status_code == 403 and not touched
    assert call(client, auth, "research_knowledge_routes.search", {"scopes": [{**SCOPE, "workspace": "main"}], "query": "x"}).status_code == 403
    issued = tokens.issue_worker(service, "draft", "draft", {"name": "worker"})
    worker = {**auth, tokens.HEADER: issued["token"]}
    for capability, data in (("research_knowledge_routes.context", {}),
            ("storyboard_routes.storyboard_read", {"nodeId": "x"}), ("opora_content_routes.listing", {})):
        assert call(client, worker, capability, data).status_code == 403


def test_canonical_binding_replay_context_and_native_null_scene_noop(setup):
    from backend.api.editor.test_research_routes import card
    client, service, auth = setup
    target = node(service)
    empty = call(client, auth, "storyboard_routes.storyboard_write",
        {"nodeId": target, "expected_revision": 0, "storyboard": None}, "empty")
    assert empty.status_code == 200 and empty.json()["result"] == {"revision": 0}
    assert call(client, auth, "research_routes.apply", {"operations": [card()]}, "source").status_code == 200
    source = {"projectId": "draft", "workspaceId": "draft", "id": card()["id"], "revision": 1}
    data = {"scopeNodeId": target, "source": source, "expectedRevision": 0, "archived": False}
    bound = call(client, auth, "research_knowledge_routes.bind", data, "bind")
    assert bound.status_code == 200, bound.text
    assert call(client, auth, "research_knowledge_routes.bind", data, "bind").json() == bound.json()
    assert call(client, auth, "research_knowledge_routes.bind", data, "stale-binding").status_code == 409
    records = call(client, auth, "research_knowledge_routes.context", {"scopeNodeId": target}).json()["result"]["records"]
    assert any(record["canonicalRef"] == source and {"relation": "shared", "scopeNodeId": target} in record["contexts"] for record in records)
