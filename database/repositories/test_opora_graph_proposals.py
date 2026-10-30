"""Scoped immutable graph records reject even self-consistent malformed content."""
import copy

import pytest

from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.test_opora_graph_proposals import graphs as graph_fixture
from backend.canvas.test_opora_graph_proposals import proposal
from backend.canvas.test_opora_graph_proposals import service as canvas_fixture

graphs, service = graph_fixture, canvas_fixture


def test_insert_requires_transaction_and_deduplicates_exact_record(graphs):
    item = proposal(graphs)
    content = {key: value for key, value in item.items() if key not in ("id", "accepted")}
    repo = graphs.repository("draft", "draft")
    with pytest.raises(RuntimeError):
        repo.insert(content)
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        assert repo.insert(content)["id"] == item["id"]
    assert len(list(repo.summaries())) == 1


@pytest.mark.parametrize("mutation", ["version", "missing", "duplicate-spec", "digest", "scope", "restricted", "goal-without-checks"])
def test_self_consistent_malformed_record_is_rejected(graphs, mutation):
    item = proposal(graphs)
    content = copy.deepcopy({key: value for key, value in item.items() if key not in ("id", "accepted")})
    if mutation == "version":
        content["schemaVersion"] = True
    elif mutation == "missing":
        del content["baseGraph"]
    elif mutation == "duplicate-spec":
        content["specifications"] *= 2
    elif mutation == "digest":
        content["graphDigest"] = "0" * 64
    elif mutation == "scope":
        content["workspace"] = "other"
    elif mutation == "restricted":
        # `checks`/`goal_mode`/`card` jsou od #180 povolená pole karty; omezené zůstává cokoli jiného.
        content["additions"]["nodes"][0]["unsupported"] = True
    else:
        content["additions"]["nodes"][0].update({"goal_mode": "until_checks_pass", "checks": []})
    identifier = content_id(content)
    repo = graphs.repository("draft", "draft")
    with repo.db:
        repo.db.execute("INSERT INTO opora_graph_proposals VALUES(?,?,?,?,?,?)",
                        ("draft", "draft", identifier, content["parentRevision"], content["createdAt"],
                         canonical({**content, "id": identifier})))
    with pytest.raises(ValueError):
        repo.read(identifier)
