from copy import deepcopy
import pytest

from backend.canvas.test_migrate_architecture import git_project
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_graph_candidate import create
from backend.canvas.opora_graph_candidate_acceptance import accept
from backend.canvas.test_opora_changesets import HUMAN, AGENT

__all__ = ["git_project"]


def baseline(canvas, project, workspace):
    native = OporaChangesets(canvas)
    context = native.context(project, workspace)
    native.baseline({"project": project, "workspace": workspace, "subject": "Synthetic scope baseline",
        "expectedAcceptedHead": None, "expectedGraphDigest": context["graphDigest"],
        "expectedSpecificationsVersion": context["specificationsVersion"]}, HUMAN)
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
    graphs = OporaGraphProposals(canvas)
    ctx = graphs.context(project, workspace)
    item = graphs.create({"project": project, "workspace": workspace, "subject": "Fixture graph baseline",
        "parentRevision": ctx["acceptedHead"], "expectedGraphDigest": ctx["graphDigest"], "plan": {"nodes": [], "edges": []}}, AGENT)
    return OporaGraphAcceptance(canvas).accept(item["id"], {"project": project, "workspace": workspace,
        "expectedAcceptedHead": ctx["acceptedHead"], "expectedGraphDigest": ctx["graphDigest"], "adoptBaseGraphDigest": item["graphDigest"]}, HUMAN)


def test_candidate_shared_architecture_and_workspace_content_authority(git_project, monkeypatch):
    canvas, project, one, two = git_project
    for workspace in (one, two):
        view = canvas.view(project, workspace)
        graph = {"nodes": [domain(), page(), node("private-" + workspace)], "edges": []}
        canvas.save_graph(project, workspace, graph, view["digest"])
        baseline(canvas, project, workspace)
    other_before = deepcopy(canvas.view(project, two)["graph"])
    head_two = OporaChangesets(canvas).context(project, two)["acceptedHead"]
    context = OporaChangesets(canvas).context(project, one)
    graph = deepcopy(canvas.view(project, one)["graph"])
    next(n for n in graph["nodes"] if n["id"] == "page")["name"] = "Shared page reviewed"
    next(n for n in graph["nodes"] if n["id"] == "private-" + one)["name"] = "Private reviewed"
    proposal = create(canvas, {"project": project, "workspace": one, "parentRevision": context["acceptedHead"],
        "expectedGraphDigest": context["graphDigest"], "subject": "Scoped full graph", "graph": graph, "undo": False,
        "operationId": "cross-workspace"}, AGENT)
    payload = {"project": project, "workspace": one, "expectedAcceptedHead": context["acceptedHead"],
        "expectedGraphDigest": context["graphDigest"], "adoptBaseGraphDigest": None, "reviewedChangesId": proposal["id"]}
    from database.repositories.opora_changesets import ChangesetRepository
    from backend.canvas.opora_graph_execution import require_accepted_graph
    architecture_before = deepcopy(canvas.architecture.read(project))
    with monkeypatch.context() as patch:
        patch.setattr(ChangesetRepository, "advance", lambda *a: (_ for _ in ()).throw(RuntimeError("injected")))
        with pytest.raises(RuntimeError, match="injected"):
            accept(canvas, proposal["id"], payload, HUMAN)
    assert canvas.architecture.read(project) == architecture_before
    assert canvas.view(project, two)["graph"] == other_before
    require_accepted_graph(canvas, project, two, head_two, other_before)
    accept(canvas, proposal["id"], payload, HUMAN)
    assert canvas.view(project, one)["graph"] == graph
    other = canvas.view(project, two)["graph"]
    assert next(n for n in other["nodes"] if n["id"] == "page")["name"] == "Shared page reviewed"
    assert next(n for n in other["nodes"] if n["id"] == "private-" + two) == next(n for n in other_before["nodes"] if n["id"] == "private-" + two)
    assert OporaChangesets(canvas).context(project, two)["acceptedHead"] == head_two
    with pytest.raises(ValueError, match="differs"):
        require_accepted_graph(canvas, project, two, head_two, other)
