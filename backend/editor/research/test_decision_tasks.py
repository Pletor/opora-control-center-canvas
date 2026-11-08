"""Native proposal acceptance, pinned provenance and retry behavior in the real database."""
import pytest

from backend.api.editor.test_research_routes import card
from backend.canvas.test_opora_changesets import service, baseline, HUMAN, AGENT
from backend.canvas.test_opora_graph_proposals import accept
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.editor.research import service as research, decisions, decision_tasks
from backend.brain_opora.determinism.gate_payloads import GateError
from database.schema.research_decisions_schema import SCHEMA

P, W = "draft", "draft"
TASKS = [{"ref": "login", "title": "Design tenant login", "goal": "Describe tenant selection and session boundaries",
          "acceptance": "Document and test tenant switching", "dependsOn": []}]


def setup(service):
    service.db_for(P).executescript(SCHEMA)
    baseline(service)
    question = card("rc_problem", kind="question")
    decision = card("rc_decision", kind="decision")
    fact = card("rc_fact", kind="finding")
    fact["verification"] = {"status": "verified", "method": "Source quote check", "at": "2026-11-08T10:00:00Z"}
    fact["sources"] = [{"ref": "https://example.org/spec", "platform": "web", "quote": "Session belongs to a tenant.",
                        "title": "Session spec", "accessedAt": "2026-11-08T10:00:00Z"}]
    research.apply(service, {"project": P, "workspace": W, "key": "init", "operations": [question, decision, fact]}, "human")
    payload = {"decisionId": "rc_decision", "decisionRevision": 1, "problemId": "rc_problem",
               "evidence": [{"id": "rc_fact", "revision": 1}], "rationale": "Tenant isolation is required",
               "assumptions": "OIDC provider available", "constraints": "No cross-tenant session"}
    return payload


def test_review_proposal_acceptance_and_reverse_links(service):
    payload = setup(service)
    review = decisions.review(service, P, W, payload, "human")
    assert decisions.review(service, P, W, payload, "human") == review
    receipt = decision_tasks.materialize(service, P, W, review["id"], TASKS, AGENT)
    assert not receipt["accepted"]
    assert receipt == decision_tasks.materialize(service, P, W, review["id"], TASKS, AGENT)
    node_id = receipt["nodeIds"]["login"]
    assert node_id not in {n["id"] for n in service.view(P, W)["graph"]["nodes"]}
    with pytest.raises(GateError):
        decision_tasks.reconcile(service, P, W, review["id"])
    graphs = OporaGraphProposals(service)
    accepted = accept(graphs, graphs.read(P, W, receipt["proposalId"]))
    result = decision_tasks.reconcile(service, P, W, review["id"])
    assert result["acceptedRevision"] == accepted["id"]
    assert result == decision_tasks.reconcile(service, P, W, review["id"])
    spec = service.node_spec(P, W, node_id)["fields"]
    assert review["id"] in spec["goal"] and "/api/research/decision-reviews/" in spec["goal"]
    assert review["evidence"][0]["id"] == "rc_fact"
    assert spec["acceptance"] == TASKS[0]["acceptance"]
    for cid in ("rc_decision", "rc_problem", "rc_fact"):
        assert research.detail(service, P, W, cid)["card"]["refs"]["nodeIds"] == [node_id]
    assert decisions.read(service, P, W, review["id"])["decision"]["revision"] == 1
    with pytest.raises(GateError):
        decision_tasks.materialize(service, P, W, review["id"], [{**TASKS[0], "goal": "Changed"}], AGENT)


def test_reject_agent_review_unknown_scope_and_unverified_evidence(service):
    payload = setup(service)
    with pytest.raises(GateError):
        decisions.review(service, P, W, payload, "agent")
    with pytest.raises(GateError):
        decisions.review(service, P, W, {**payload, "evidence": [{"id": "rc_problem", "revision": 1}]}, "human")
    review = decisions.review(service, P, W, payload, "human")
    with pytest.raises((GateError, ValueError)):
        decisions.read(service, P, "foreign", review["id"])
    with pytest.raises(GateError):
        decisions.review(service, P, W, {**payload, "rationale": "Changed"}, "human")


def test_existing_task_reuses_identity_through_native_spec_proposal(service):
    from backend.canvas.opora_acceptance import OporaAcceptance
    payload = setup(service)
    review = decisions.review(service, P, W, payload, "human")
    tasks = [{**TASKS[0], "nodeId": "a"}]
    before = [n["id"] for n in service.view(P, W)["graph"]["nodes"]]
    receipt = decision_tasks.materialize(service, P, W, review["id"], tasks, AGENT)
    changes = OporaGraphProposals(service).specifications
    accepted = OporaAcceptance(service).accept(receipt["proposalId"], {"project": P, "workspace": W,
                    "expectedAcceptedHead": changes.context(P, W)["acceptedHead"]}, HUMAN)
    assert decision_tasks.reconcile(service, P, W, review["id"])["acceptedRevision"] == accepted["id"]
    assert [n["id"] for n in service.view(P, W)["graph"]["nodes"]] == before
    assert review["id"] in service.node_spec(P, W, "a")["fields"]["goal"]


def test_process_interruption_recovers_the_same_native_proposal(service, monkeypatch):
    payload = setup(service)
    review = decisions.review(service, P, W, payload, "human")
    original = OporaGraphProposals.create
    captured = []
    def interrupted(self, payload, by):
        result = original(self, payload, by)
        captured.append(result)
        raise RuntimeError("process interrupted after native commit")
    monkeypatch.setattr(OporaGraphProposals, "create", interrupted)
    with pytest.raises(RuntimeError):
        decision_tasks.materialize(service, P, W, review["id"], TASKS, AGENT)
    assert decision_tasks.status(service, P, W, review["id"])["pending"]
    with pytest.raises(GateError):
        decision_tasks.materialize(service, P, W, review["id"], [{**TASKS[0], "title": "Different"}], AGENT)
    monkeypatch.setattr(OporaGraphProposals, "create", original)
    recovered = decision_tasks.materialize(service, P, W, review["id"], TASKS, AGENT)
    assert recovered["proposalId"] == captured[0]["id"]
    assert recovered["nodeIds"] == captured[0]["refs"]
    assert len(OporaGraphProposals(service).list(P, W)["items"]) == 1


def test_invalid_dependencies_and_unknown_existing_identity_do_not_create_tasks(service):
    review = decisions.review(service, P, W, setup(service), "human")
    tasks = [{**TASKS[0], "ref": "one", "dependsOn": ["two"]},
             {**TASKS[0], "ref": "two", "dependsOn": ["one"]}]
    with pytest.raises(GateError):
        decision_tasks.materialize(service, P, W, review["id"], tasks, AGENT)
    with pytest.raises(GateError):
        decision_tasks.materialize(service, P, W, review["id"], [{**TASKS[0], "nodeId": "foreign"}], AGENT)
    assert OporaGraphProposals(service).list(P, W)["items"] == []


def test_http_decision_review_and_task_authorization(tmp_path):
    from backend.api.editor.test_brief_vault_routes import client_with_sector
    from backend.editor.node.test_removals import HEADERS, SCOPE
    from backend.brain_opora.determinism import tokens
    with client_with_sector(tmp_path) as client:
        service = client.app.state.service
        payload = setup(service)
        _, token = tokens.issue_heart(service, P, W)
        agent = {**HEADERS, "X-Opora-Actor": "agent; name=heart", tokens.HEADER: token}
        endpoint = "/api/research/decision-reviews"
        denied = client.post(endpoint, json={**SCOPE, "review": payload}, headers=agent)
        assert denied.status_code == 403, denied.text
        reviewed = client.post(endpoint, json={**SCOPE, "review": payload}, headers=HEADERS)
        assert reviewed.status_code == 200, reviewed.text
        rid = reviewed.json()["id"]
        restored = client.get(endpoint, params={**SCOPE, "decisionId": payload["decisionId"]}, headers=HEADERS)
        assert restored.status_code == 200, restored.text
        assert restored.json() == {"reviews": [reviewed.json()]}
        task_url = endpoint + "/" + rid + "/tasks"
        proposed = client.post(task_url, json={**SCOPE, "tasks": TASKS}, headers=agent)
        assert proposed.status_code == 200, proposed.text
        assert proposed.json()["accepted"] is False
        assert client.get(task_url, params=SCOPE, headers=agent).status_code == 200
        assert client.get(task_url, params={**SCOPE, "workspace": "foreign"}, headers=agent).status_code == 403
        assert client.post(endpoint + "/" + rid + "/reconcile", json=SCOPE, headers=agent).status_code == 409


def test_existing_spec_constraints_criteria_and_steps_are_preserved(service):
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.opora_acceptance import OporaAcceptance
    payload = setup(service)
    changes = OporaChangesets(service)
    context = changes.context(P, W)
    fields = {"goal": "Original purpose", "non_goals": "Never store passwords", "acceptance": "Existing acceptance test",
              "steps": [{"id": "original", "order": 1, "title": "Original step", "acceptance": ["Original proof"], "dependsOn": []}]}
    proposal = changes.create({"project": P, "workspace": W, "parentRevision": context["acceptedHead"],
                               "expectedGraphDigest": context["graphDigest"], "subject": "Original assignment",
                               "changes": [{"nodeId": "a", "expectedRevision": 0, "fields": fields}]}, HUMAN)
    OporaAcceptance(service).accept(proposal["id"], {"project": P, "workspace": W,
                                   "expectedAcceptedHead": context["acceptedHead"]}, HUMAN)
    review = decisions.review(service, P, W, payload, "human")
    receipt = decision_tasks.materialize(service, P, W, review["id"], [{**TASKS[0], "nodeId": "a"}], AGENT)
    proposed = changes.read(P, W, receipt["proposalId"])["changes"][0]["fields"]
    assert fields["goal"] in proposed["goal"]
    assert fields["non_goals"] in proposed["non_goals"]
    assert fields["acceptance"] in proposed["acceptance"]
    assert proposed["steps"][0] == fields["steps"][0]
    assert len(proposed["steps"]) == 2


def test_native_rebase_retains_identity_and_can_reconcile_acceptance(service):
    from backend.canvas.test_opora_graph_proposals import proposal
    review = decisions.review(service, P, W, setup(service), "human")
    receipt = decision_tasks.materialize(service, P, W, review["id"], TASKS, AGENT)
    graphs = OporaGraphProposals(service)
    accept(graphs, proposal(graphs, "Unrelated accepted work"))
    context = graphs.context(P, W)
    moved = graphs.rebase(receipt["proposalId"], {"project": P, "workspace": W,
                           "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"]}, AGENT)
    accepted = accept(graphs, moved)
    result = decision_tasks.reconcile(service, P, W, review["id"])
    assert result["nodeIds"] == receipt["nodeIds"]
    assert result["acceptedRevision"] == accepted["id"]
    assert result["acceptedProposalId"] == moved["id"]


@pytest.mark.parametrize("revision", [None, True, False, 0, -1, 1.0, "1"])
def test_review_rejects_implicit_or_non_integer_pins(service, revision):
    payload = setup(service)
    with pytest.raises(GateError):
        decisions.review(service, P, W, {**payload, "decisionRevision": revision}, "human")
    with pytest.raises(GateError):
        decisions.review(service, P, W, {**payload, "evidence": [{"id": "rc_fact", "revision": revision}]}, "human")


def test_long_review_uses_compact_native_context_reference(service):
    payload = setup(service)
    payload.update(rationale="R" * 8000, assumptions="A" * 8000, constraints="C" * 8000)
    review = decisions.review(service, P, W, payload, "human")
    tasks = [{**TASKS[0], "goal": "G" * 3500}]
    receipt = decision_tasks.materialize(service, P, W, review["id"], tasks, AGENT)
    proposed = OporaGraphProposals(service).read(P, W, receipt["proposalId"])
    goal = proposed["specifications"][0]["fields"]["goal"]
    assert len(goal) <= 4000 and tasks[0]["goal"] in goal and review["id"] in goal
    assert decisions.read(service, P, W, review["id"])["rationale"] == payload["rationale"]


def test_existing_task_update_cannot_pretend_to_change_dependencies(service):
    review = decisions.review(service, P, W, setup(service), "human")
    tasks = [{**TASKS[0], "ref": "one", "nodeId": "a", "dependsOn": ["two"]},
             {**TASKS[0], "ref": "two", "nodeId": "b"}]
    with pytest.raises(GateError, match="native graph proposal"):
        decision_tasks.materialize(service, P, W, review["id"], tasks, AGENT)


def test_new_review_cannot_duplicate_task_before_reverse_link_reconciliation(service):
    payload = setup(service)
    first_review = decisions.review(service, P, W, payload, "human")
    first = decision_tasks.materialize(service, P, W, first_review["id"], TASKS, AGENT)
    graphs = OporaGraphProposals(service)
    accept(graphs, graphs.read(P, W, first["proposalId"]))
    # Native task exists, but the deliberately omitted reconcile has not updated research refs.
    current = research.detail(service, P, W, "rc_decision")["card"]
    assert current["refs"]["nodeIds"] == []
    from backend.editor.research import model
    updated = {"op": "card", "id": current["id"], "expectedRevision": current["revision"],
               **{key: current[key] for key in model.CARD}, "summary": "Clarified decision rationale"}
    research.apply(service, {"project": P, "workspace": W, "key": "clarify", "operations": [updated]}, "human")
    second_review = decisions.review(service, P, W, {**payload, "decisionRevision": 2}, "human")
    with pytest.raises(GateError, match="instead of duplicating"):
        decision_tasks.materialize(service, P, W, second_review["id"], TASKS, AGENT)
    replay = decision_tasks.materialize(service, P, W, first_review["id"], TASKS, AGENT)
    assert replay["proposalId"] == first["proposalId"] and replay["nodeIds"] == first["nodeIds"]
    reused = decision_tasks.materialize(service, P, W, second_review["id"],
                                       [{**TASKS[0], "nodeId": first["nodeIds"]["login"]}], AGENT)
    assert reused["proposalKind"] == "spec" and reused["nodeIds"] == first["nodeIds"]


def test_materialization_considers_current_refs_after_review_snapshot(service):
    from backend.editor.research import model
    review = decisions.review(service, P, W, setup(service), "human")
    current = research.detail(service, P, W, "rc_decision")["card"]
    updated = {"op": "card", "id": current["id"], "expectedRevision": current["revision"],
               **{key: current[key] for key in model.CARD}, "refs": {**current["refs"], "nodeIds": ["a"]}}
    research.apply(service, {"project": P, "workspace": W, "key": "link-existing", "operations": [updated]}, "human")
    assert review["decision"]["refs"]["nodeIds"] == []
    with pytest.raises(GateError, match="instead of duplicating"):
        decision_tasks.materialize(service, P, W, review["id"], TASKS, AGENT)


def test_native_task_ref_validation_happens_before_durable_intent(service):
    review = decisions.review(service, P, W, setup(service), "human")
    with pytest.raises(ValueError, match="ref musí"):
        decision_tasks.materialize(service, P, W, review["id"], [{**TASKS[0], "ref": "task_invalid"}], AGENT)
    assert service.db_for(P).execute("SELECT COUNT(*) FROM research_materializations").fetchone()[0] == 0
    corrected = decision_tasks.materialize(service, P, W, review["id"], [{**TASKS[0], "ref": "task-valid"}], AGENT)
    assert "task-valid" in corrected["nodeIds"]
