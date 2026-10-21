"""Malformed history, stale state and concurrent review cannot publish unreviewed changes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.test_opora_changesets import AGENT, SCOPE
from backend.canvas.test_opora_graph_change_state import install
from backend.canvas.test_opora_graph_changes import approve, change, edits, graphs, service
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.node.test_removals import state_node

__all__ = ["edits", "graphs", "service"]


def test_state_only_rebase_refreshes_unrelated_state_but_not_affected(edits, service):
    item = change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Reviewed"}}]})
    state = deepcopy(DesktopV3State(service).current("draft", "draft")["state"])
    state["nodes"]["b"] = state_node()
    install(service, state)
    with pytest.raises(ValueError, match="state changed"):
        approve(edits, item)
    context = edits.context(**SCOPE)
    rebased = edits.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                      "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert rebased["stateEffects"]["revision"] == 1
    state["nodes"]["a"] = state_node()
    install(service, state, 2)
    with pytest.raises(ValueError, match="Affected state"):
        edits.rebase(rebased["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                   "expectedGraphDigest": context["graphDigest"]}, AGENT)


def test_record_corruption_rejected_even_if_hash_recomputed(edits):
    item = change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Reviewed"}}]})
    repo = edits.repository("draft", "draft")
    mutations = [lambda value: value.update(schemaVersion=True),
                 lambda value: value["changes"]["nodes"][0].update(operation="remove"),
                 lambda value: value["stateEffects"].update(checkedNodeIds=[]),
                 lambda value: value["resultGraph"]["nodes"].clear()]
    for mutation in mutations:
        changed = {key: deepcopy(value) for key, value in item.items() if key not in ("id", "accepted")}
        mutation(changed)
        identity = content_id(changed)
        record = {**changed, "id": identity}
        repo.db.execute("INSERT INTO opora_graph_proposals VALUES(?,?,?,?,?,?)",
                        ("draft", "draft", identity, item["parentRevision"], item["createdAt"], canonical(record)))
        repo.db.commit()
        with pytest.raises(ValueError):
            repo.read(identity)


def test_concurrent_duplicate_acceptance_publishes_one_revision(edits):
    item = change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Concurrent"}}]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve(edits, item), range(2)))
    assert results[0]["id"] == results[1]["id"]
    db = edits.service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_spec_revisions WHERE proposal_id=?", (item["id"],)).fetchone()[0] == 1
