from backend.brain_opora.determinism import milestone_next_work, milestones, snapshot
from backend.brain_opora.determinism.test_milestone_evidence import integration, result, submit
from backend.brain_opora.determinism.test_milestones import close, service
from backend.brain_opora.determinism.test_snapshot import FACTS
from database.repositories.intake_milestones import IntakeMilestones

__all__ = ["service", "integration"]


def active(service, made):
    db = service.db_for("draft")
    return [milestones.evaluate(db, "draft", IntakeMilestones(db).get(made["id"]))]


def test_next_work_prefers_current_milestone_and_excludes_unrelated_extension(service, integration):
    authority, record, made, _ = integration
    authority.release(record["executionId"], {"project": "draft", "workspace": "draft", "token": record["token"], "epoch": record["epoch"]})
    steps = milestone_next_work.collect(service, "draft", "draft", active(service, made))
    assert steps[0]["nodeId"] == "n1" and steps[0]["status"] == "ready"
    assert {item["nodeId"] for item in steps} == {"n1", "n2", "n3"}
    assert steps[1]["status"] == "needs_specification"
    assert all(item["acceptedRevision"] for item in steps)
    rendered = snapshot.render({**FACTS, "nextMilestoneWork": steps})
    assert rendered.index("DALŠÍ PRÁCE MILNÍKU") < rendered.index("PLÁN:")
    assert "Nerozšiřuj nesouvisející větev" in rendered
    assert "n1 · realize · ready" in rendered


def test_active_run_is_inspected_instead_of_duplicate_realization(service, integration):
    _, _, made, _ = integration
    work = milestone_next_work.collect(service, "draft", "draft", active(service, made))
    running = next(item for item in work if item["nodeId"] == "n1")
    assert running["status"] == "in_progress" and running["action"] == "inspect_run"


def test_reported_result_is_inspected_instead_of_duplicate_realization(service, integration):
    authority, record, made, proof = integration
    submit(authority, record, result(proof))
    work = milestone_next_work.collect(service, "draft", "draft", active(service, made))
    reported = next(item for item in work if item["nodeId"] == "n1")
    assert reported["status"] == "reported" and reported["action"] == "inspect_result"


def test_no_edge_card_with_unaccepted_document_or_graph_drift_is_not_ready(service, integration):
    from copy import deepcopy
    authority, record, made, _ = integration
    authority.release(record["executionId"], {"project": "draft", "workspace": "draft", "token": record["token"], "epoch": record["epoch"]})
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    next(node for node in graph["nodes"] if node["id"] == "n1")["purpose"] = "Unaccepted change"
    service.save_graph("draft", "draft", graph, view["digest"])
    work = milestone_next_work.collect(service, "draft", "draft", active(service, made))
    assert next(item for item in work if item["nodeId"] == "n1")["status"] == "blocked"
    service.save_graph("draft", "draft", view["graph"], service.view("draft", "draft")["digest"])
    spec = service.node_spec("draft", "draft", "n1")
    service.node_spec("draft", "draft", "n1", {"project": "draft", "workspace": "draft", "node": "n1",
        "expected_revision": spec["revision"], "fields": {**spec["fields"], "goal": "Unaccepted specification"}})
    work = milestone_next_work.collect(service, "draft", "draft", active(service, made))
    assert next(item for item in work if item["nodeId"] == "n1")["status"] == "blocked"


def test_next_work_exposes_exact_blocking_input_instead_of_suggesting_execution(service, integration):
    from backend.canvas.test_opora_executions import accept_graph_change
    _, _, made, _ = integration
    accept_graph_change(service, {"edges": [{"from": "@n1", "to": "@n2", "port": "rule", "relation": "requires",
        "requirement": {"readiness": "implemented", "revision": 0}}]})
    work = milestone_next_work.collect(service, "draft", "draft", active(service, made))
    blocked = next(item for item in work if item["nodeId"] == "n1")
    assert blocked["status"] == "blocked" and blocked["action"] == "resolve_input"
    assert "n2" in blocked["blockers"][0]


def test_closed_cards_leave_integration_gap_until_pinned_positive_negative_proof(service, integration):
    authority, record, made, proof = integration
    close(service, "n1", "n2", "n3")
    steps = milestone_next_work.collect(service, "draft", "draft", active(service, made))
    assert len(steps) == 1 and steps[0]["action"] == "verify_integration"
    assert steps[0]["pinnedRevision"] == proof["acceptedRevision"]
    # Reopen while the existing execution reports; reporting itself never marks cards done.
    close(service)
    submit(authority, record, result(proof))
    close(service, "n1", "n2", "n3")
    assert milestone_next_work.collect(service, "draft", "draft", active(service, made)) == []
