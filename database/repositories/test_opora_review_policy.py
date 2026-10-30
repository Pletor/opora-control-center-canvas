"""Immutable policy storage keeps strict values, CAS and transaction ownership."""
import sqlite3
from copy import deepcopy

import pytest

from backend.canvas.opora_review_policy_validation import rules, validate_policy
from database.repositories.opora_review_policy import Policies
from database.schema.opora_review_policy_schema import SCHEMA

RULES = {"requiredChecks": [{"appId": 8, "name": "tests"}], "reviewerIds": [2], "minimumCodeApprovals": 1,
         "minimumPlanApprovals": 1, "maxObservationAgeSeconds": 300}


def content(parent=None, **updates):
    return {"schemaVersion": 1, "kind": "review-policy", "project": "project", "workspace": "workspace",
            "parentPolicyRevision": parent, "enabled": True, "repository": {"id": 10, "fullName": "owner/repo", "baseBranch": "main"},
            "identityEvidenceId": "a" * 40, "rules": deepcopy(RULES), "by": {"kind": "human", "name": "Reviewer"},
            "createdAt": "2026-10-21T10:00:00Z", **updates}


@pytest.fixture
def repo(tmp_path):
    db = sqlite3.connect(tmp_path / "policy.sqlite")
    db.executescript(SCHEMA)
    yield Policies(db, "project", "workspace")
    db.close()


@pytest.mark.parametrize("key,value", [
    ("requiredChecks", []), ("requiredChecks", [{"appId": True, "name": "tests"}]),
    ("requiredChecks", [{"appId": 9007199254740992, "name": "tests"}]),
    ("requiredChecks", [{"appId": 8, "name": ""}]), ("requiredChecks", [{"appId": 8, "name": "x" * 256}]),
    ("requiredChecks", [{"appId": 8, "name": "tests"}] * 2),
    ("reviewerIds", []), ("reviewerIds", [2, 2]), ("reviewerIds", [True]),
    ("reviewerIds", list(range(1, 102))), ("minimumCodeApprovals", True),
    ("minimumPlanApprovals", 2), ("minimumPlanApprovals", 0),
    ("maxObservationAgeSeconds", 29), ("maxObservationAgeSeconds", 3601),
])
def test_strict_rule_bounds(key, value):
    with pytest.raises(ValueError):
        rules({**RULES, key: value})


def test_rule_canonicalization_keeps_exact_case_and_spaces():
    result = rules({**RULES, "requiredChecks": [{"appId": 9, "name": " Tests "}, {"appId": 8, "name": "tests"}], "reviewerIds": [3, 2]})
    assert result["requiredChecks"] == [{"appId": 8, "name": "tests"}, {"appId": 9, "name": " Tests "}]
    assert result["reviewerIds"] == [2, 3]
    with pytest.raises(ValueError):
        rules({**RULES, "verdict": "passed"})


def test_activation_cas_disable_and_rollback(repo):
    with pytest.raises(RuntimeError):
        repo.activate(content(), None)
    repo.db.execute("BEGIN IMMEDIATE")
    first = repo.activate(content(), None)
    assert repo.db.in_transaction and repo.head() == first["id"]
    repo.db.rollback()
    assert repo.head() is None and repo.history() == []
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        first = repo.activate(content(), None)
    with pytest.raises(ValueError, match="head changed"), repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        repo.activate(content(), None)
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        disabled = repo.activate(content(first["id"], enabled=False), first["id"])
    assert repo.head() == disabled["id"] and not repo.read(disabled["id"])["enabled"]
    assert repo.read(first["id"])["enabled"] and len(repo.history()) == 2


def test_scope_hash_and_index_corruption_fail_closed(repo):
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        first = repo.activate(content(), None)
    with pytest.raises(ValueError):
        Policies(repo.db, "project", "other").read(first["id"])
    repo.db.execute("UPDATE opora_review_policies SET parent_id=?", ("f" * 40,))
    with pytest.raises(ValueError, match="integrity"):
        repo.head()


# Úložiště od plné autonomie (#137) přijímá `agent` pod jeho jménem; bránu „jen člověk“ drží služba (acts_as_human). Cizí druh původce odmítá dál.
@pytest.mark.parametrize("updates", [{"schemaVersion": True}, {"enabled": 1}, {"repository": {"id": True, "fullName": "owner/repo", "baseBranch": "main"}},
                                      {"by": {"kind": "bot", "name": "Worker"}}, {"createdAt": "2026-10-21T10:00:00"}])
def test_stored_policy_shape_is_strict(updates):
    with pytest.raises(ValueError):
        validate_policy(content(**updates))
