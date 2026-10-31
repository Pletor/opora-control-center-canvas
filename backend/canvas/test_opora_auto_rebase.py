"""Auto-rebase merges disjoint changes, marks redundant ones and records true conflicts."""
import pytest

from backend.canvas.opora_auto_rebase import AutoRebase
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.test_opora_changesets import (
    AGENT,
    FIELDS,
    HUMAN,
    SCOPE,
    accept,
    baseline,
    service,
)
from database.repositories.opora_auto_rebase import AutoRebaseStore

__all__ = ["service"]


def propose(service, node="a", **fields):
    changesets = OporaChangesets(service)
    current = changesets.context("draft", "draft")
    documents = {item["nodeId"]: item for item in current["documents"]}
    accepted = {item["nodeId"]: item for item in current["acceptedDocuments"]}
    return changesets.create({**SCOPE, "subject": "Edit " + node, "parentRevision": current["acceptedHead"],
                              "expectedGraphDigest": current["graphDigest"],
                              "changes": [{"nodeId": node, "expectedRevision": documents[node]["revision"],
                                           "fields": {**accepted[node]["fields"], **fields}}]}, AGENT)


@pytest.fixture
def started(service):
    return baseline(service)


def test_disjoint_cards_and_fields_rebase_to_new_system_proposal(service, started):
    first = propose(service, "a", goal="Goal A")
    other_card = propose(service, "b", goal="Goal B")
    other_field = propose(service, "a", acceptance="Acceptance A")
    head = accept(service, first, started["id"])["id"]
    summary = AutoRebase(service).run("draft", "draft")
    assert {item["proposalId"] for item in summary["rebased"]} == {other_card["id"], other_field["id"]}
    changesets = OporaChangesets(service)
    moved = {item["proposalId"]: changesets.read("draft", "draft", item["resultId"]) for item in summary["rebased"]}
    rebased = moved[other_field["id"]]
    assert rebased["parentRevision"] == head and rebased["supersedes"] == other_field["id"]
    assert rebased["by"] == {"kind": "orchestrator", "name": "system"}
    assert rebased["changes"][0]["fields"] == {**FIELDS, "goal": "Goal A", "acceptance": "Acceptance A"}
    assert changesets.read("draft", "draft", other_field["id"])["parentRevision"] == started["id"]
    outcome = AutoRebaseStore(service.db_for("draft"), "draft", "draft").outcome("spec", other_field["id"], head)
    assert outcome["outcome"] == "rebased" and outcome["reason"] == "three_way_clean"
    final = accept(service, rebased, head)
    assert service.node_spec("draft", "draft", "a")["fields"]["goal"] == "Goal A"
    assert service.node_spec("draft", "draft", "a")["fields"]["acceptance"] == "Acceptance A"
    assert final["parentRevision"] == head


def test_identical_change_is_marked_redundant_without_new_proposal(service, started):
    first = propose(service, "a", goal="Same goal")
    twin = propose(service, "a", goal="Same goal", non_goals="")
    head = accept(service, first, started["id"])["id"]
    summary = AutoRebase(service).run("draft", "draft")
    assert [item["proposalId"] for item in summary["redundant"]] == [twin["id"]]
    assert summary["rebased"] == [] and summary["conflicts"] == []
    store = AutoRebaseStore(service.db_for("draft"), "draft", "draft")
    assert store.outcome("spec", twin["id"], head)["outcome"] == "redundant"
    assert twin["id"] in store.redundant()


def test_same_field_conflict_records_base_ours_theirs_and_stays_stale(service, started):
    first = propose(service, "a", goal="Ours")
    sibling = propose(service, "a", goal="Theirs")
    head = accept(service, sibling, started["id"])["id"]
    rebase = AutoRebase(service)
    summary = rebase.run("draft", "draft")
    assert [item["proposalId"] for item in summary["conflicts"]] == [first["id"]]
    conflicts = rebase.conflicts("draft", "draft", "open")["items"]
    assert len(conflicts) == 1
    item = conflicts[0]["items"][0]
    assert item["key"] == "spec:a:goal" and item["ours"] == "Ours" and item["theirs"] == "Theirs"
    assert item["base"] == FIELDS["goal"] or item["base"] != "Ours"
    assert OporaChangesets(service).read("draft", "draft", first["id"])["parentRevision"] == started["id"]
    resolution = propose(service, "a", goal="Ours and theirs")
    with pytest.raises(ValueError, match="different proposal"):
        rebase.resolve(conflicts[0]["id"], {**SCOPE, "resolutionProposalId": first["id"]}, AGENT)
    resolved = rebase.resolve(conflicts[0]["id"], {**SCOPE, "resolutionProposalId": resolution["id"]}, AGENT)
    assert resolved["status"] == "resolved" and resolved["resolutionProposalId"] == resolution["id"]
    assert resolution["parentRevision"] == head


def test_run_is_idempotent_and_bounded(service, started):
    first = propose(service, "a", goal="Goal A")
    stale = [propose(service, "b", goal=f"B{index}") for index in range(3)]
    accept(service, first, started["id"])
    rebase = AutoRebase(service)
    one = rebase.run("draft", "draft", limit=2)
    assert len(one["rebased"]) == 2 and one["remaining"] == 1
    two = rebase.run("draft", "draft", limit=2)
    assert len(two["rebased"]) == 1 and two["remaining"] == 0
    again = rebase.run("draft", "draft")
    assert again["rebased"] == again["redundant"] == again["conflicts"] == again["skipped"] == []
    rows = service.db_for("draft").execute("SELECT COUNT(*) FROM opora_spec_proposals").fetchone()[0]
    assert rows == 1 + len(stale) + 3


def test_conflict_becomes_obsolete_when_head_moves_again(service, started):
    first = propose(service, "a", goal="Ours")
    sibling = propose(service, "a", goal="Theirs")
    later = propose(service, "b", goal="Later")
    head = accept(service, sibling, started["id"])["id"]
    rebase = AutoRebase(service)
    summary = rebase.run("draft", "draft")
    assert len(summary["conflicts"]) == 1
    moved = next(item["resultId"] for item in summary["rebased"] if item["proposalId"] == later["id"])
    accept(service, OporaChangesets(service).read("draft", "draft", moved), head)
    rebase.run("draft", "draft")
    states = {item["acceptedHead"]: item["status"] for item in rebase.conflicts("draft", "draft")["items"]
              if item["proposalId"] == first["id"]}
    assert states[head] == "obsolete"
    reopened = rebase.conflicts("draft", "draft", "open")["items"]
    assert len(reopened) == 1 and reopened[0]["acceptedHead"] != head


def test_auto_rebase_never_accepts(service, started):
    first = propose(service, "a", goal="Goal A")
    propose(service, "b", goal="Goal B")
    head = accept(service, first, started["id"])["id"]
    AutoRebase(service).run("draft", "draft")
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] == head
    assert HUMAN["kind"] == "human"


def open_conflict(service, started):
    first = propose(service, "a", goal="Ours")
    sibling = propose(service, "a", goal="Theirs")
    head = accept(service, sibling, started["id"])["id"]
    rebase = AutoRebase(service)
    rebase.run("draft", "draft")
    return rebase, rebase.conflicts("draft", "draft", "open")["items"][0], head, first


def test_keep_accepted_resolves_without_proposal_and_leaves_head(service, started):
    rebase, conflict, head, first = open_conflict(service, started)
    resolved = rebase.resolve(conflict["id"], {**SCOPE, "keep": "accepted"}, AGENT)
    assert resolved["status"] == "resolved" and resolved["resolutionProposalId"] is None
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] == head
    assert service.node_spec("draft", "draft", "a")["fields"]["goal"] == "Theirs"
    with pytest.raises(ValueError, match="open conflict"):
        rebase.resolve(conflict["id"], {**SCOPE, "keep": "accepted"}, AGENT)
    assert first["id"] in {item["proposalId"] for item in rebase.conflicts("draft", "draft", "resolved")["items"]}


def test_keep_accepted_rejects_conflict_from_older_head(service, started):
    rebase, conflict, head, _ = open_conflict(service, started)
    accept(service, propose(service, "b", goal="Later"), head)
    with pytest.raises(ValueError, match="older accepted head"):
        rebase.resolve(conflict["id"], {**SCOPE, "keep": "accepted"}, AGENT)
    assert rebase.conflict("draft", "draft", conflict["id"])["status"] == "open"


@pytest.mark.parametrize("fields", [{}, {"keep": "accepted", "resolutionProposalId": "0" * 40}, {"keep": "ours"}])
def test_resolve_needs_exactly_one_way(service, started, fields):
    rebase, conflict, _, _ = open_conflict(service, started)
    with pytest.raises(ValueError):
        rebase.resolve(conflict["id"], {**SCOPE, **fields}, AGENT)
