"""Graph changes use real Git authority across restarts and revalidate sources."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_change_acceptance import OporaGraphChangeAcceptance
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.test_opora_changesets import AGENT, HUMAN
from backend.canvas.test_opora_graph_git import git_graphs, prepared

__all__ = ["git_graphs"]


def edit(service, scope, plan):
    changes = OporaGraphChanges(service)
    context = changes.context(**scope)
    item = changes.create({**scope, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                           "subject": "Git reviewed change", "plan": plan}, AGENT)
    return item, {**scope, "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                  "adoptBaseGraphDigest": None, "reviewedChangesId": item["id"]}


def test_git_edit_and_restart_preserve_source_file_and_fence_old_execution(git_graphs):
    service, scope, original, data = git_graphs
    item, payload = prepared(service, scope)
    baseline = OporaGraphAcceptance(service).accept(item["id"], payload, HUMAN)
    node = item["refs"]["new"]
    executions = ExecutionResults(service)
    context = executions.context(**scope, node=node)
    claim = executions.claim({**scope, "nodeId": node, "requestId": "before-edit", "ttlSeconds": 900,
        "expectedAcceptedHead": baseline["id"], "expectedContextVersion": context["contextVersion"]}, "agent:worker")
    changed, payload = edit(service, scope, {"updateNodes": [{"id": node, "fields": {"name": "Reviewed Git task"}}]})
    accepted = OporaGraphChangeAcceptance(service).accept(changed["id"], payload, HUMAN)
    with pytest.raises(ValueError):
        executions.submit(claim["executionId"], {**scope, "token": claim["token"], "epoch": claim["epoch"],
            "requestId": "late-result", "result": {"summary": "Stale work"}})
    assert service.graph_file(*scope.values()).read_bytes() == original
    fresh = CanvasService(data)
    try:
        context = OporaGraphChanges(fresh).context(**scope)
        assert context["acceptedHead"] == accepted["id"]
        assert next(item for item in context["workingGraph"]["nodes"] if item["id"] == node)["name"] == "Reviewed Git task"
        assert ExecutionResults(fresh).context(**scope, node=node)["available"]
    finally:
        fresh.close()


def test_source_update_is_rechecked_before_acceptance(git_graphs):
    service, scope, original, _ = git_graphs
    item, payload = prepared(service, scope)
    OporaGraphAcceptance(service).accept(item["id"], payload, HUMAN)
    plan = {"updateNodes": [{"id": item["refs"]["new"], "fields": {"parentId": "sector",
            "sourceRef": {"origin": "existing", "kind": "file", "path": "README.md"}}}]}
    changed, payload = edit(service, scope, plan)
    (service.workspace_sources.root(*scope.values()) / "README.md").unlink()
    with pytest.raises(ValueError):
        OporaGraphChangeAcceptance(service).accept(changed["id"], payload, HUMAN)
    assert service.graph_file(*scope.values()).read_bytes() == original
