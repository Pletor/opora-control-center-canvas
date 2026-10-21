"""A valid raw accepted child remains visible when SQL rewind is prohibited."""
import copy
import sqlite3

import pytest

from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from database.repositories.opora_changesets import ChangesetRepository


def test_related_hash_valid_raw_child_cannot_be_hidden_by_reference_aba(sparse):
    _, authority, refs = sparse
    record = claimed(sparse)
    db = authority.canvas.db_for("draft")
    repo = ChangesetRepository(db, *SCOPE.values())
    origin = repo.read(record["acceptedRevision"])
    content = {key: copy.deepcopy(value) for key, value in origin.items() if key != "id"}
    content.update(kind="acceptance", parentRevision=origin["id"], proposalId="f" * 40, subject="Raw accepted child")
    next(doc for doc in content["documents"] if doc["nodeId"] == refs["a"])["fields"]["goal"] = "Relevant change"
    with db:
        db.execute("BEGIN IMMEDIATE")
        child = repo.insert(content)
        assert repo.read(child["id"])["id"] == child["id"]
        repo.advance(origin["id"], child["id"])
        with pytest.raises(sqlite3.IntegrityError, match="scoped child"):
            repo.advance(child["id"], origin["id"])
    with pytest.raises(ValueError, match="changed"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})


def test_normal_acceptance_after_context_preparation_advances_scoped_child(sparse):
    graphs, authority, refs = sparse
    record = claimed(sparse)
    accepted = accept_spec(graphs.service, propose_spec(graphs.service, nodes=(refs["b"],)), record["acceptedRevision"])
    renewed = authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
    assert renewed["contextValidation"]["checkedAcceptedRevision"] == accepted["id"]
