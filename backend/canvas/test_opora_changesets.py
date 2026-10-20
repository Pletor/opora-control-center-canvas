"""Real specification changes remain proposals until a transactional human acceptance."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_acceptance import OporaAcceptance
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page

HUMAN = {"kind": "human", "name": "Reviewer"}
AGENT = {"kind": "agent", "name": "Builder"}
SCOPE = {"project": "draft", "workspace": "draft"}
FIELDS = {"goal": "New goal", "non_goals": "", "acceptance": "Test passes"}


@pytest.fixture
def service(tmp_path):
    instance = CanvasService(tmp_path / "data")
    current = instance.view("draft", "draft")
    instance.save_graph("draft", "draft", {"nodes": [node("a"), node("b"), domain(), page()], "edges": []},
                        current["digest"])
    yield instance
    instance.close()


def baseline(service):
    changesets = OporaChangesets(service)
    current = changesets.context("draft", "draft")
    return changesets.baseline({**SCOPE, "subject": "Initial specifications", "expectedAcceptedHead": None,
                                "expectedGraphDigest": current["graphDigest"],
                                "expectedSpecificationsVersion": current["specificationsVersion"]}, HUMAN)


def propose(service, nodes=("a",), goal="New goal"):
    changesets = OporaChangesets(service)
    current = changesets.context("draft", "draft")
    documents = {item["nodeId"]: item for item in current["documents"]}
    return changesets.create({**SCOPE, "subject": goal, "parentRevision": current["acceptedHead"],
                              "expectedGraphDigest": current["graphDigest"],
                              "changes": [{"nodeId": node_id, "expectedRevision": documents[node_id]["revision"],
                                           "fields": {**FIELDS, "goal": goal}} for node_id in nodes]}, AGENT)


def accept(service, proposal, head):
    return OporaAcceptance(service).accept(proposal["id"], {**SCOPE, "expectedAcceptedHead": head}, HUMAN)


def legacy_save(service, node_id="a", goal="Working edit"):
    current = service.node_spec("draft", "draft", node_id)
    return service.node_spec("draft", "draft", node_id, {**SCOPE, "node": node_id,
                             "expected_revision": current["revision"], "fields": {**FIELDS, "goal": goal}})


def test_siblings_do_not_write_canvas_and_independent_rebase_creates_new_immutable_object(service):
    initial = baseline(service)
    first, second = propose(service), propose(service, ("b",))
    changesets = OporaChangesets(service)
    assert first["parentRevision"] == second["parentRevision"] == initial["id"]
    assert service.node_spec("draft", "draft", "a")["revision"] == 0
    assert service.node_spec("draft", "draft", "b")["revision"] == 0
    revision = accept(service, first, initial["id"])
    with pytest.raises(ValueError, match="přenos"):
        accept(service, second, revision["id"])
    moved = changesets.rebase(second["id"], {**SCOPE, "expectedAcceptedHead": revision["id"]}, AGENT)
    assert moved["supersedes"] == second["id"] and moved["parentRevision"] == revision["id"]
    assert changesets.read("draft", "draft", second["id"]) == second
    final = accept(service, moved, revision["id"])
    assert final["parentRevision"] == revision["id"]
    assert service.node_spec("draft", "draft", "b")["fields"] == FIELDS
    assert changesets.read("draft", "draft", first["id"])["accepted"] is True


def test_same_card_sibling_conflict_cannot_rebase(service):
    initial = baseline(service)
    first, second = propose(service), propose(service, goal="Conflicting goal")
    revision = accept(service, first, initial["id"])
    with pytest.raises(ValueError, match="dotčené"):
        OporaChangesets(service).rebase(second["id"], {**SCOPE, "expectedAcceptedHead": revision["id"]}, AGENT)


def test_legacy_edit_invalidates_existing_proposal_and_new_proposal_reconciles_only_its_target(service):
    initial = baseline(service)
    old = propose(service)
    legacy_save(service)
    legacy_save(service, "b", "Unaccepted other edit")
    with pytest.raises(ValueError, match="dotčené"):
        accept(service, old, initial["id"])
    fresh = propose(service, goal="Reviewed reconciliation")
    assert fresh["changes"][0]["before"]["goal"] == "Working edit"
    assert fresh["changes"][0]["acceptedBefore"]["fields"]["goal"] == ""
    accepted = accept(service, fresh, initial["id"])
    b = next(item for item in accepted["documents"] if item["nodeId"] == "b")
    assert b["fields"]["goal"] == ""
    assert service.node_spec("draft", "draft", "b")["fields"]["goal"] == "Unaccepted other edit"
    assert OporaChangesets(service).context("draft", "draft")["workingDiffers"] is True


def test_concurrent_acceptance_advances_once(service):
    initial, barrier = baseline(service), Barrier(2)
    proposed = propose(service)

    def run(_):
        barrier.wait(timeout=5)
        try:
            return accept(service, proposed, initial["id"])["id"]
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        result = list(workers.map(run, range(2)))
    assert sum(item is not None for item in result) == 1
    assert service.node_spec("draft", "draft", "a")["revision"] == 1


def test_second_document_failure_rolls_back_first_and_accepted_pointer(service, monkeypatch):
    initial = baseline(service)
    proposed = propose(service, ("a", "b"))
    save = service.specs.save_in_transaction

    def fail_second(scope, revision, fields):
        if scope[2] == "b":
            raise RuntimeError("Injected second document failure")
        return save(scope, revision, fields)

    monkeypatch.setattr(service.specs, "save_in_transaction", fail_second)
    with pytest.raises(RuntimeError, match="second"):
        accept(service, proposed, initial["id"])
    assert service.node_spec("draft", "draft", "a")["revision"] == 0
    changesets = OporaChangesets(service)
    assert changesets.context("draft", "draft")["acceptedHead"] == initial["id"]
    assert not changesets.read("draft", "draft", proposed["id"])["accepted"]


def test_architecture_spec_uses_its_real_owner_and_survives_restart(service, tmp_path):
    initial = baseline(service)
    proposed = propose(service, ("page",))
    assert proposed["changes"][0]["ownerWorkspace"] == "architecture"
    accepted = accept(service, proposed, initial["id"])
    assert service.specs.read(("draft", "architecture", "page"))["fields"] == FIELDS
    assert service.specs.read(("draft", "draft", "page"))["revision"] == 0
    service.close()
    restarted = CanvasService(tmp_path / "data")
    try:
        changesets = OporaChangesets(restarted)
        assert changesets.context("draft", "draft")["acceptedHead"] == accepted["id"]
        assert changesets.read("draft", "draft", proposed["id"])["changes"] == proposed["changes"]
        assert restarted.node_spec("draft", "draft", "page")["fields"] == FIELDS
    finally:
        restarted.close()


def test_baseline_cannot_replace_an_existing_accepted_revision(service):
    initial = baseline(service)
    with pytest.raises(ValueError, match="již existuje"):
        baseline(service)
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] == initial["id"]


def test_proposal_can_accept_exact_legacy_working_edit(service):
    initial = baseline(service)
    legacy_save(service)
    proposed = propose(service, goal="Working edit")
    assert proposed["changes"][0]["fields"] == proposed["changes"][0]["before"]
    accepted = accept(service, proposed, initial["id"])
    assert next(item for item in accepted["documents"] if item["nodeId"] == "a")["fields"]["goal"] == "Working edit"
    assert not OporaChangesets(service).context("draft", "draft")["workingDiffers"]


def test_graph_changes_reject_acceptance_without_spec_write(service):
    initial = baseline(service)
    proposed = propose(service)
    current = service.view("draft", "draft")
    import copy
    changed = copy.deepcopy(current["graph"])
    changed["nodes"][0]["name"] = "Changed context"
    service.save_graph("draft", "draft", changed, current["digest"])
    with pytest.raises(ValueError, match="Graf"):
        accept(service, proposed, initial["id"])
    assert service.node_spec("draft", "draft", "a")["revision"] == 0


def test_failure_after_accepted_ref_update_rolls_back_every_write(service, monkeypatch):
    from database.repositories.opora_changesets import ChangesetRepository

    initial = baseline(service)
    proposed = propose(service)
    advance = ChangesetRepository.advance

    def fail_after_advance(repo, expected, identifier):
        advance(repo, expected, identifier)
        raise RuntimeError("Injected acceptance failure")

    monkeypatch.setattr(ChangesetRepository, "advance", fail_after_advance)
    with pytest.raises(RuntimeError, match="acceptance failure"):
        accept(service, proposed, initial["id"])
    changesets = OporaChangesets(service)
    assert changesets.context("draft", "draft")["acceptedHead"] == initial["id"]
    assert not changesets.read("draft", "draft", proposed["id"])["accepted"]
    assert service.node_spec("draft", "draft", "a")["revision"] == 0


def test_empty_baseline_is_rejected_without_reference_or_revision_write(tmp_path):
    empty = CanvasService(tmp_path / "empty")
    try:
        with pytest.raises(ValueError, match="Nejprve vytvořte kartu"):
            baseline(empty)
        assert OporaChangesets(empty).context("draft", "draft")["acceptedHead"] is None
        assert empty.db_for("draft").execute("SELECT COUNT(*) FROM opora_spec_revisions").fetchone()[0] == 0
        assert empty.db_for("draft").execute("SELECT COUNT(*) FROM opora_spec_refs").fetchone()[0] == 0
    finally:
        empty.close()
