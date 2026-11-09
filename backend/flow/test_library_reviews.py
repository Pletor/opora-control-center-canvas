"""Actual native library operations remain scoped, reviewable and atomic."""
import pytest

from backend.app.factory import create_app
from backend.flow import library, library_reviews as reviews, workflows
from backend.flow.test_simulate import bmi_graph, OK_CASE
from backend.canvas.payload_errors import NextStep
from backend.brain_opora.determinism.gate_payloads import GateError
from database.schema.library_review_schema import SCHEMA

AUTHOR = {"kind": "agent", "name": "heart"}


@pytest.fixture
def data(tmp_path):
    service = create_app(tmp_path / "data").state.service
    service.db.executescript(SCHEMA)
    project = service.project_hub.empty_project({"name": "Own", "confirmed": True})["id"]
    return service, project


def submit(data, operation, payload, key="request"):
    service, project = data
    return reviews.submit(service, project, "draft", AUTHOR, operation, payload, key)


def decide(data, record, action="accept"):
    return reviews.decide(data[0], data[1], "draft", record["id"], action)


def source(data):
    service, _ = data
    folder = library.create_folder(service.db, "agent", "proof", "Proof")
    flow = library.create_flow(service.db, folder["id"], "source", "Source")
    version = workflows.create_draft(service.db, flow["id"], bmi_graph([OK_CASE]))
    workflows.activate(service.db, workflows.set_candidate(service.db, version["id"])["id"])
    return folder, library.flow_detail(service.db, flow["id"])


def test_human_folder_review_replay_reject_and_scope(data):
    service, project = data
    payload = {"owner": "human", "slug": "review-proof", "title": "Review proof"}
    before = library.list_library(service.db, "human")
    record = submit(data, "folder_create", payload)
    assert record["status"] == "pending" and record["requiresHuman"]
    assert library.list_library(service.db, "human") == before
    assert submit(data, "folder_create", payload) == record
    with pytest.raises(NextStep):
        submit(data, "folder_create", {**payload, "title": "Changed"})
    with pytest.raises(workflows.FlowNotFound):
        reviews.read(service, project, "other", record["id"])
    rejected = decide(data, record, "reject")
    assert rejected["status"] == "rejected" and decide(data, record, "reject") == rejected
    assert library.list_library(service.db, "human") == before
    with pytest.raises(NextStep):
        decide(data, record)


def test_agent_direct_and_human_folder_create_update_delete(data):
    service, _ = data
    direct = submit(data, "folder_create", {"owner": "agent", "slug": "direct", "title": "Direct"})
    assert direct["status"] == "applied" and not direct["requiresHuman"]
    pending = submit(data, "folder_create", {"owner": "human", "slug": "review", "title": "Review"}, "human")
    accepted = decide(data, pending)
    assert accepted == decide(data, pending)
    identifier = accepted["result"]["id"]
    update = submit(data, "folder_update", {"folder_id": identifier, "title": "Revised"}, "update")
    assert library.get_folder(service.db, identifier)["title"] == "Review"
    assert decide(data, update)["result"]["title"] == "Revised"
    deletion = submit(data, "folder_delete", {"folder_id": identifier}, "delete")
    assert decide(data, deletion)["result"] == {"deleted": identifier}


def test_stale_folder_changes_do_not_overwrite(data):
    service, _ = data
    folder = library.list_library(service.db, "human")[0]
    pending = submit(data, "folder_update", {"folder_id": folder["id"], "title": "Proposal"})
    library.update_folder(service.db, folder["id"], "Human edit")
    with pytest.raises(NextStep, match="changed"):
        decide(data, pending)
    assert library.get_folder(service.db, folder["id"])["title"] == "Human edit"
    assert reviews.read(service, data[1], "draft", pending["id"])["status"] == "pending"


def test_create_contribute_adopt_promote_reuse_native_versions_and_lineage(data):
    service, project = data
    folder, flow = source(data)
    human = library.list_library(service.db, "human")[0]
    empty = submit(data, "flow_create", {"folder": human["id"], "slug": "empty", "title": "Empty"})
    assert decide(data, empty)["result"]["versions"] == []
    adopted = submit(data, "flow_adopt", {"workflow_id": flow["id"]}, "adopt")
    assert adopted["status"] == "applied" and adopted["result"]["projectId"] == project
    contribution = submit(data, "flow_contribute", {"workflow_id": adopted["result"]["id"], "folder": human["id"], "slug": "published", "title": "Published"}, "contribute")
    assert contribution["status"] == "pending"
    result = decide(data, contribution)["result"]
    assert result["versions"][0]["graph"] == flow["versions"][0]["graph"]
    assert result["derivedFrom"]["workflowId"] == adopted["result"]["id"]
    promotion = submit(data, "flow_promote", {"workflow_id": flow["id"], "folder": human["id"]}, "promote")
    assert library.part_of(service.db, flow["id"]) == "agent"
    assert decide(data, promotion)["result"]["id"] == flow["id"]
    assert library.part_of(service.db, flow["id"]) == "human"


def test_foreign_source_and_missing_node_fail_before_any_receipt(data):
    service, _ = data
    folder, flow = source(data)
    foreign = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
    other = library.adopt(service.db, flow["id"], foreign)
    with pytest.raises(GateError):
        submit(data, "flow_contribute", {"workflow_id": other["id"], "folder": folder["id"], "slug": "leak", "title": "Leak"})
    with pytest.raises(GateError):
        submit(data, "flow_adopt", {"workflow_id": flow["id"], "nodeId": "foreign-node"})
    assert service.db.execute("SELECT COUNT(*) FROM flow_library_reviews").fetchone()[0] == 0


def test_source_version_change_conflicts_and_copy_failure_rolls_back_all_native_rows(data, monkeypatch):
    service, _ = data
    _, flow = source(data)
    human = library.list_library(service.db, "human")[0]
    payload = {"workflow_id": flow["id"], "folder": human["id"], "slug": "copy", "title": "Copy"}
    pending = submit(data, "flow_contribute", payload)
    version = workflows.create_draft(service.db, flow["id"], bmi_graph([OK_CASE]))
    workflows.activate(service.db, workflows.set_candidate(service.db, version["id"])["id"])
    with pytest.raises(NextStep):
        decide(data, pending)
    fresh = submit(data, "flow_contribute", payload, "fresh")
    before = [tuple(row) for row in service.db.execute("SELECT * FROM flow_workflows")]
    def fail(*args, **kwargs):
        raise RuntimeError("injected after workflow insert")
    monkeypatch.setattr(library, "create_draft", fail)
    with pytest.raises(RuntimeError, match="injected"):
        decide(data, fresh)
    assert [tuple(row) for row in service.db.execute("SELECT * FROM flow_workflows")] == before
    assert reviews.read(service, data[1], "draft", fresh["id"])["status"] == "pending"
