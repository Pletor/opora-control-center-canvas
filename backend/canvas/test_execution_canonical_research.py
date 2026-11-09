"""Canonical pins survive source updates and never widen worker source permissions."""
import json
from copy import deepcopy

import pytest

from backend.api.editor.test_research_routes import card
from backend.canvas.test_execution_write_set import configure, start
from backend.canvas.test_opora_changesets import service
from backend.editor.research import knowledge, service as research
from backend.editor.research.scope_evidence import collect

SCOPE = {"project": "draft", "workspace": "draft"}


def source(service):
    research.apply(service, {**SCOPE, "key": "source", "operations": [card("shared")]}, "human")
    ref = {"projectId": "draft", "workspaceId": "draft", "id": "shared", "revision": 1}
    bindings = [knowledge.bind(service, "draft", "draft", node, ref, 0, False, lambda *_: None, "human")
                for node in ("login", "identity")]
    return ref, bindings


@pytest.mark.parametrize("protocol", [1, 2])
def test_one_canonical_pin_two_scopes_exact_revision_result(service, protocol):
    authority = configure(service)
    ref, bindings = source(service)
    execution = start(authority, protocol)
    assignment = deepcopy(execution["assignment"])
    pins = assignment["researchEvidence"]["canonicalScopes"]["pins"]
    [pin] = [pin for pin in pins if pin["canonicalRef"] == ref]
    assert len(pin["bindings"]) == 2
    assert {item["id"] for item in pin["bindings"]} == {item["id"] for item in bindings}
    assert pin["availability"] == "pinned" and pin["digest"]
    research.apply(service, {**SCOPE, "key": "source-new", "operations": [card("shared", expectedRevision=1,
        content="New source revision")]}, "human")
    receipt = authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
        "requestId": "result", "result": {"summary": "Uses historical source"}})
    assert receipt["acceptedRevision"] == execution["acceptedRevision"]
    assert receipt["assignmentDigest"] == execution["assignmentDigest"]
    assert authority.read_assignment(execution["executionId"], **SCOPE, token=execution["token"])["assignment"] == assignment


@pytest.mark.parametrize("protocol", [1, 2])
def test_binding_archive_rejects_result_without_replacing_pin(service, protocol):
    authority = configure(service)
    ref, _ = source(service)
    execution = start(authority, protocol)
    assignment = deepcopy(execution["assignment"])
    knowledge.bind(service, "draft", "draft", "login", ref, 1, True, lambda *_: None, "human")
    with pytest.raises(ValueError, match="binding selection changed"):
        authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
            "requestId": "result", "result": {"summary": "Stale binding"}})
    assert authority.read_assignment(execution["executionId"], **SCOPE, token=execution["token"])["assignment"] == assignment


def test_foreign_reference_is_pinned_without_reading_source(service, monkeypatch):
    configure(service)
    db = service.db_for("draft")
    binding = {"id": "foreign", "revision": 1, "scopeNodeId": "login", "source": {
        "projectId": "secret", "workspaceId": "draft", "id": "private", "revision": 7}, "archived": False, "by": "human", "at": "now"}
    with db:
        db.execute("INSERT INTO research_scope_bindings VALUES(?,?,?,?,?,?)", ("draft", "draft", "login", "foreign", 1, json.dumps(binding)))
    original = service.db_for
    def guarded(project):
        assert project == "draft", "Foreign source database must never be opened"
        return original(project)
    monkeypatch.setattr(service, "db_for", guarded)
    from backend.editor.research import scope_evidence
    monkeypatch.setattr(scope_evidence, "_source", lambda *_: (_ for _ in ()).throw(AssertionError("Foreign source was dereferenced")))
    [pin] = collect(db, "draft", "draft", ["login"])["pins"]
    assert pin["canonicalRef"] == binding["source"]
    assert pin["availability"] == "source_scope_not_delegated"
    assert "digest" not in pin and "provenance" not in pin
    assert "content" not in str(pin) and "title" not in str(pin)


@pytest.mark.parametrize("protocol", [1, 2])
def test_adding_first_binding_after_claim_is_controlled_conflict(service, protocol):
    authority = configure(service)
    research.apply(service, {**SCOPE, "key": "other-source", "operations": [card("source", refs={
        **card()["refs"], "nodeIds": ["b"]})]}, "human")
    execution = start(authority, protocol)
    ref = {"projectId": "draft", "workspaceId": "draft", "id": "source", "revision": 1}
    knowledge.bind(service, "draft", "draft", "login", ref, 0, False, lambda *_: None, "human")
    with pytest.raises(ValueError, match="binding selection changed"):
        authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
            "requestId": "result", "result": {"summary": "Unexpected new input"}})


@pytest.mark.parametrize("protocol", [1, 2])
def test_binding_change_between_preparation_and_claim_is_rejected(service, protocol):
    from backend.canvas.opora_execution_context import prepare
    authority = configure(service)
    ref, _ = source(service)
    context = prepare(authority, {**SCOPE, "nodeId": "a", "contextProtocolVersion": 2}) if protocol == 2 else authority.context(**SCOPE, node="a")
    knowledge.bind(service, "draft", "draft", "login", ref, 1, True, lambda *_: None, "human")
    with pytest.raises(ValueError, match="assignment changed"):
        authority.claim({**SCOPE, "nodeId": "a", "requestId": "binding-race", "ttlSeconds": 60,
            "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"],
            **({"contextProtocolVersion": 2} if protocol == 2 else {})}, "agent:worker")
