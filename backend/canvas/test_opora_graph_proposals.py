"""Graph additions remain immutable until one atomic human acceptance."""
import copy

import pytest

from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE, baseline
from backend.canvas.test_opora_changesets import service as canvas_fixture
from database.repositories.opora_changesets import ChangesetRepository
from database.schema.opora_graph_schema import SCHEMA

service = canvas_fixture


@pytest.fixture
def graphs(service):
    service.db_for("draft").executescript(SCHEMA)
    baseline(service)
    return OporaGraphProposals(service)


def proposal(graphs, name="New card", plan=None):
    context = graphs.context(**SCOPE)
    return graphs.create({**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                          "subject": name, "plan": plan or {"nodes": [{"ref": "new", "kind": "node", "name": name}]}}, AGENT)


def accept(graphs, item, **overrides):
    context = graphs.context(**SCOPE)
    return OporaGraphAcceptance(graphs.service).accept(item["id"], {**SCOPE,
        "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
        "adoptBaseGraphDigest": item["graphDigest"] if item["requiresBaseAdoption"] else None, **overrides}, HUMAN)


def test_proposal_is_immutable_acceptance_has_manifest_and_default_documents(graphs, service):
    before = copy.deepcopy(service.view("draft", "draft"))
    item = proposal(graphs)
    node_id = item["refs"]["new"]
    assert service.view("draft", "draft")["graph"] == before["graph"]
    assert item["requiresBaseAdoption"] and not item["accepted"]
    with pytest.raises(ValueError, match="Explicit adoption"):
        accept(graphs, item, adoptBaseGraphDigest=None)
    result = accept(graphs, item)
    assert any(node["id"] == node_id for node in service.view("draft", "draft")["graph"]["nodes"])
    document = next(doc for doc in result["documents"] if doc["nodeId"] == node_id)
    assert document["revision"] == 1 and document["fields"] == {"goal": "", "non_goals": "", "acceptance": ""}
    assert result["graphManifestId"] and graphs.read(**SCOPE, record_id=item["id"])["accepted"]
    later = accept(graphs, proposal(graphs, "Later"))
    assert accept(graphs, item)["id"] == result["id"]
    assert graphs.context(**SCOPE)["acceptedHead"] == later["id"]


def test_area_with_position_is_stored_after_an_accepted_graph(graphs):
    """Pozice (x, y) se uloží jako JSON seznam; návrh po přijatém grafu nesmí spadnout na „identity conflict“."""
    accept(graphs, proposal(graphs))
    item = proposal(graphs, "Area", {"nodes": [{"ref": "zone", "kind": "area", "name": "Zone", "size": {"w": 600, "h": 400},
                                                "position": {"x": 40, "y": 60}}]})
    zone = item["refs"]["zone"]
    assert item["positions"] == {zone: [40, 60]}
    assert graphs.read(**SCOPE, record_id=item["id"])["positions"] == item["positions"]


def test_sibling_rebase_preserves_ids_and_creates_new_object(graphs, service):
    left, right = proposal(graphs, "Left"), proposal(graphs, "Right")
    accept(graphs, left)
    with pytest.raises(ValueError, match="rebase"):
        accept(graphs, right)
    context = graphs.context(**SCOPE)
    moved = graphs.rebase(right["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                      "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert moved["id"] != right["id"] and moved["refs"] == right["refs"]
    assert moved["supersedes"] == right["id"] and not moved["requiresBaseAdoption"]
    accept(graphs, moved)
    ids = {node["id"] for node in service.view("draft", "draft")["graph"]["nodes"]}
    assert {left["refs"]["new"], right["refs"]["new"]} <= ids


def test_failure_after_graph_and_documents_rolls_back_everything(graphs, service, monkeypatch):
    item = proposal(graphs)
    before, head = copy.deepcopy(service.view("draft", "draft")["graph"]), graphs.context(**SCOPE)["acceptedHead"]
    def fail(*args):
        raise RuntimeError("injected ref failure")
    monkeypatch.setattr(ChangesetRepository, "advance", fail)
    with pytest.raises(RuntimeError, match="injected"):
        accept(graphs, item)
    assert service.view("draft", "draft")["graph"] == before
    assert graphs.context(**SCOPE)["acceptedHead"] == head
    db = service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_graph_manifests").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM node_spec_revisions WHERE node_id=?", (item["refs"]["new"],)).fetchone()[0] == 0


@pytest.mark.parametrize("field", ["site", "gateNodeId"])
def test_forbidden_addition_fields_are_rejected_before_build(graphs, field):
    with pytest.raises(ValueError, match="Unsupported"):
        proposal(graphs, plan={"nodes": [{"ref": "x", "kind": "node", "name": "X", field: "value"}]})


def test_list_is_sparse_and_detail_scope_checked(graphs):
    item = proposal(graphs)
    summary = graphs.list(**SCOPE)["items"][0]
    assert summary["nodeCount"] == 1 and "baseGraph" not in summary and "specifications" not in summary
    with pytest.raises(ValueError):
        graphs.read("draft", "elsewhere", item["id"])


def test_later_plan_wires_a_block_port_of_an_accepted_card(graphs, service):
    """Druhá dávka nad přijatým grafem: blok s portem přijde `extend` dávky plánu, vazba `block` z něj návrhem grafu."""
    from backend.canvas.canvas_plan import apply_plan
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    first = proposal(graphs, "Decision")
    accept(graphs, first)
    card = first["refs"]["new"]
    revision = DesktopV3State(service).read("draft", "draft")["revision"]
    placed = apply_plan(service, {**SCOPE, "digest": service.view("draft", "draft")["digest"], "plan": {"extend": [
        {"node": f"@{card}", "expectedRevision": revision,
         "blocks": [{"ref": "pick", "title": "Varianta", "ports": [{"ref": "yes", "label": "Ano → další"}]}]}]}})
    block = placed["blocks"][f"@{card}/pick"]
    wired = proposal(graphs, "Follow-up", {"nodes": [{"ref": "next", "kind": "node", "name": "Follow-up"}],
                                           "edges": [{"from": f"@{card}", "to": "next", "port": "block",
                                                      "block": block, "blockPort": "yes"}]})
    accept(graphs, wired)
    edge = next(edge for edge in service.view("draft", "draft")["graph"]["edges"] if edge.get("port") == "block")
    assert (edge["source"], edge["target"]) == (card, wired["refs"]["next"])
    assert (edge["sourceBlockId"], edge["sourcePortId"]) == (block, "yes")
    with pytest.raises(ValueError, match="nemá port"):
        proposal(graphs, "Bad", {"edges": [{"from": f"@{card}", "to": f"@{card}", "port": "block", "block": block,
                                            "blockPort": "no"}]})
    before = service.view("draft", "draft")
    accepted_head = graphs.context(**SCOPE)["acceptedHead"]
    with pytest.raises(ValueError, match="Neplatn\u00e1 vazba"):
        proposal(graphs, "Rule", {"edges": [{"from": f"@{card}", "to": f"@{card}", "port": "rule"}]})
    observed = service.view("draft", "draft")
    assert (observed["graph"], observed["digest"]) == (before["graph"], before["digest"])
    assert graphs.context(**SCOPE)["acceptedHead"] == accepted_head
    # Native rule links are valid between distinct cards; only the self-edge was invalid.
    semantic = proposal(graphs, "Rule link", {"edges": [
        {"from": f"@{card}", "to": "@" + wired["refs"]["next"], "port": "rule"}]})
    observed = service.view("draft", "draft")
    assert (observed["graph"], observed["digest"]) == (before["graph"], before["digest"])
    accept(graphs, semantic)
    assert any(item["source"] == card and item["target"] == wired["refs"]["next"] and item["port"] == "rule"
               for item in service.view("draft", "draft")["graph"]["edges"])
