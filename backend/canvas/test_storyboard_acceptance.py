from copy import deepcopy

import pytest

from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.opora_content_acceptance import OporaContentAcceptance
from backend.canvas.test_opora_changesets import HUMAN, AGENT, service
from backend.canvas.test_execution_write_set import configure, start, SCOPE
from backend.editor.storyboard.storyboard import StoryboardService
from backend.editor.storyboard.test_storyboard import board
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords


def accept_scene(canvas, node, value=None):
    scenes = StoryboardService(canvas)
    if value is None:
        value = scenes.read("draft", "draft", node)["storyboard"]
    repo = ChangesetRepository(canvas.db_for("draft"), "draft", "draft")
    proposal = OporaContentChanges(canvas).create({**SCOPE, "expectedAcceptedHead": repo.head(), "subject": "Storyboard contract",
        "changes": [{"kind": "storyboard", "target": node, "field": "storyboard", "value": value}]}, AGENT)
    return OporaContentAcceptance(canvas).accept(proposal["id"], {**SCOPE, "expectedAcceptedHead": proposal["parentRevision"],
        "reviewedProposalId": proposal["id"], "adoptBaseContentDigest": proposal["baseContentDigest"] if proposal["requiresBaseContentAdoption"] else None}, HUMAN)


@pytest.mark.parametrize("protocol", [1, 2])
def test_accepted_storyboard_native_contract_and_selective_staleness(service, protocol):
    authority = configure(service)
    scenes = StoryboardService(service)
    scenes.save({**SCOPE, "nodeId": "login", "expected_revision": 0, "storyboard": board(title="Approved login")})
    with pytest.raises(ValueError):
        start(authority, protocol)
    accepted = accept_scene(service, "login")
    execution = start(authority, protocol)
    original = deepcopy(execution["assignment"])
    pin = next(item for item in original["storyboards"] if item["nodeId"] == "login")
    assert pin["acceptance"] == "accepted-content"
    assert pin["acceptedRevision"] == accepted["id"] and pin["contentManifestId"] == accepted["contentManifestId"]
    assert scenes.read("draft", "draft", "login", pin["revision"])["storyboard"] == pin["storyboard"]
    # A sibling outside the affected/input closure must not invalidate this run.
    from backend.canvas.test_opora_executions import accept_graph_change
    accept_graph_change(service, {"nodes": [{"ref": "sibling", "kind": "node", "name": "Sibling"}]})
    sibling = next(item["id"] for item in service.view("draft", "draft")["graph"]["nodes"] if item["name"] == "Sibling")
    scenes.save({**SCOPE, "nodeId": sibling, "expected_revision": 0, "storyboard": board(title="Other branch")})
    receipt = authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
        "requestId": "result", "result": {"summary": "Approved scene implemented"}})
    assert receipt["assignmentDigest"] == execution["assignmentDigest"]
    scenes.save({**SCOPE, "nodeId": "login", "expected_revision": pin["revision"], "storyboard": board(title="New draft")})
    from backend.canvas.storyboard_evidence import validate_db
    with pytest.raises(ValueError, match="changed"):
        validate_db(service.db_for("draft"), "draft", "draft", original["storyboards"])
    assert authority.read_assignment(execution["executionId"], **SCOPE, token=execution["token"])["assignment"] == original


def test_native_content_acceptance_rolls_back_storyboard_source_and_head(service, monkeypatch):
    configure(service)
    scenes = StoryboardService(service)
    scenes.save({**SCOPE, "nodeId": "login", "expected_revision": 0, "storyboard": board(title="Before")})
    before = scenes.read("draft", "draft", "login")
    repo = ChangesetRepository(service.db_for("draft"), "draft", "draft")
    head = repo.head()
    original = ContentRecords.insert
    def fail_manifest(self, value, *, manifest=False):
        if manifest:
            raise ValueError("forced manifest rollback")
        return original(self, value, manifest=manifest)
    monkeypatch.setattr(ContentRecords, "insert", fail_manifest)
    with pytest.raises(ValueError, match="forced"):
        accept_scene(service, "login", board(title="After"))
    assert scenes.read("draft", "draft", "login") == before
    assert repo.head() == head
    assert service.db_for("draft").execute("SELECT COUNT(*) FROM storyboard_revisions").fetchone()[0] == 1


@pytest.mark.parametrize("protocol", [1, 2])
def test_historical_captured_assignments_keep_exact_digest_and_do_not_gain_approval(service, protocol, monkeypatch):
    authority = configure(service)
    scenes = StoryboardService(service)
    scenes.save({**SCOPE, "nodeId": "login", "expected_revision": 0, "storyboard": board(title="Legacy working input")})
    from backend.canvas import storyboard_evidence
    native = storyboard_evidence.collect
    # Reproduce the old binary's capture contract, not an accepted-content claim.
    with monkeypatch.context() as old:
        old.setattr(storyboard_evidence, "collect", lambda *args, **_: native(*args[:5]))
        execution = start(authority, protocol)
    original = deepcopy(execution["assignment"])
    assert all(pin["acceptance"] == "captured-at-claim" for pin in original["storyboards"])
    receipt = authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
        "requestId": "legacy-result", "result": {"summary": "Historical captured input result"}})
    assert receipt["assignmentDigest"] == execution["assignmentDigest"]
    assert authority.read_assignment(execution["executionId"], **SCOPE, token=execution["token"])["assignment"] == original


def test_restoring_historical_scene_creates_new_native_and_accepted_revision(service):
    configure(service)
    first = accept_scene(service, "login", board(title="First accepted behavior"))
    scenes = StoryboardService(service)
    original = scenes.read("draft", "draft", "login", 1)["storyboard"]
    second = accept_scene(service, "login", board(title="Second behavior"))
    restored = accept_scene(service, "login", original)
    assert len({first["id"], second["id"], restored["id"]}) == 3
    assert scenes.read("draft", "draft", "login")["revision"] == 3
    assert scenes.read("draft", "draft", "login", 1)["storyboard"] == original
    assert scenes.read("draft", "draft", "login")["storyboard"]["title"] == original["title"]


def test_manifest_reads_are_bounded_per_revision_not_per_scene_pin(service, monkeypatch):
    configure(service)
    accepted = accept_scene(service, "login", board(title="Bounded source capture"))
    from backend.canvas.storyboard_evidence import collect, validate_db
    original = ContentRecords.read
    reads = []
    def counted(self, identifier, *, manifest=False):
        if manifest:
            reads.append(identifier)
        return original(self, identifier, manifest=manifest)
    monkeypatch.setattr(ContentRecords, "read", counted)
    graph = service.view("draft", "draft")["graph"]
    pins = collect(service, "draft", "draft", ["a", "login", "identity", "tenant"], graph, accepted["id"])
    # One read validates the Changeset's child integrity, one builds the index.
    assert reads == [accepted["contentManifestId"]] * 2
    reads.clear()
    validate_db(service.db_for("draft"), "draft", "draft", pins)
    assert reads == [accepted["contentManifestId"]] * 2


def test_accepted_revision_is_read_once_per_process(monkeypatch):
    # Přijatá revize je neměnná: druhá karta téže revize repozitář znovu nečte (agent-state Ample: 941 čtení).
    from backend.canvas import storyboard_evidence
    from database.repositories import opora_changesets, opora_content_records
    reads = []
    monkeypatch.setattr(storyboard_evidence, "ACCEPTED", {})
    monkeypatch.setattr(opora_changesets.ChangesetRepository, "read",
                        lambda self, revision: reads.append(revision) or {"contentManifestId": "m1"})
    monkeypatch.setattr(opora_content_records.ContentRecords, "read", lambda self, identifier, **_: {
        "entries": [{"kind": "storyboard", "target": "a", "revision": 1, "value": {}}]})
    first = storyboard_evidence._accepted(None, "p", "w", "rev1", "a", {}, shared=True)
    second = storyboard_evidence._accepted(None, "p", "w", "rev1", "b", {}, shared=True)
    assert first[0]["target"] == "a" and second == (None, "m1") and reads == ["rev1"]
    storyboard_evidence._accepted(None, "p", "w", "rev2", "a", {}, shared=True)
    storyboard_evidence._accepted(None, "p", "w", "rev1", "a", {})  # kontrola pinu čte vždy znovu
    assert reads == ["rev1", "rev2", "rev1"]

