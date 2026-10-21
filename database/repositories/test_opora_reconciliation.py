"""Stored history validation and transaction ownership resist tampering and cross-binding facts."""
from copy import deepcopy

import pytest

from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.reconciliation_test_support import data, setup
from database.repositories.opora_reconciliation_jobs import stamp


def test_caller_transaction_and_scoped_identity_validation(tmp_path):
    db, repo, _, binding = setup(tmp_path / "project.sqlite")
    content = {"schemaVersion": 1, "project": "project", "workspace": "workspace",
               "bindingId": binding["id"], "createdAt": stamp(1002), "data": data(binding)}
    with pytest.raises(RuntimeError, match="transaction"):
        repo.insert("observation", content)
    with db:
        db.execute("BEGIN IMMEDIATE")
        wrong = deepcopy(content)
        wrong["data"]["pr"]["id"] += 1
        with pytest.raises(ValueError, match="identity"):
            repo.insert("observation", wrong)
        incomplete = deepcopy(content)
        incomplete["data"]["pr"]["mergeCommitSha"] = None
        with pytest.raises(ValueError):
            repo.insert("observation", incomplete)
        result = repo.insert("observation", content)
    assert repo.read("observation", result["id"])["data"]["pr"]["headRepoId"] is None
    db.close()


def test_rehashed_malformed_binding_and_projection_tampering_reject(tmp_path):
    db, repo, _, binding = setup(tmp_path / "project.sqlite")
    with db:
        db.execute("UPDATE opora_reconciliation_refs SET generation=2")
    with pytest.raises(ValueError, match="projection"):
        repo.latest_control(binding["id"])
    # Even an attacker recomputing a hash cannot bless a malformed authority shape.
    content = {k: v for k, v in binding.items() if k != "id"}
    content["pr"]["id"] = True
    identifier = content_id(content)
    with db:
        db.execute("UPDATE opora_reconciliation_records SET id=?,binding_id=?,content=? WHERE id=?",
                   (identifier, identifier, canonical({**content, "id": identifier}), binding["id"]))
    with pytest.raises(ValueError, match="safe integer"):
        repo.read("binding", identifier)
    db.close()


def test_event_unique_key_is_database_enforced_and_links_same_binding(tmp_path):
    db, repo, _, binding = setup(tmp_path / "project.sqlite")
    from backend.canvas.opora_reconciliation_finish import semantic
    common = {"schemaVersion": 1, "project": "project", "workspace": "workspace",
              "bindingId": binding["id"], "createdAt": stamp(1002)}
    with db:
        db.execute("BEGIN IMMEDIATE")
        observation = repo.insert("observation", {**common, "data": data(binding)})
        merged = data(binding)["pr"]
        key = content_id({"repositoryId": binding["repository"]["id"], "prId": binding["pr"]["id"],
                          "mergedAt": merged["mergedAt"], "mergeCommitSha": merged["mergeCommitSha"]})
        content = {**common, "eventKey": key, "observationId": observation["id"],
                   "fromState": None, "toState": semantic(data(binding))}
        first = repo.insert("event", content)
        assert repo.event_for_key(binding["id"], key) == first
        with pytest.raises(ValueError):
            repo.insert("event", {**content, "createdAt": stamp(1003)})
        assert len(repo.records("event", binding["id"])) == 1
    db.close()
