"""Merge gate read model: approvals bound to the exact head, agents never count, agent-state integration."""
import pytest

from backend.canvas import opora_agent_state_reviews as reviews
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_review_gate import read_review_gates
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_jobs import CONFIG, push, run_finders, run_voters
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401
from backend.canvas.test_opora_review_jobs import found
from backend.canvas.test_opora_review_status import snapshot
from database.repositories.opora_review_evidence import ReviewEvidenceRepository

SENSITIVE = ((".github/workflows/ci.yml", 3, 1),)  # medium tier → one human approval


def approval(user=2, sha=SHA, state="APPROVED", user_type="User", review_id=None, minute=0):
    return {"id": review_id or user * 10 + minute, "userId": user, "login": f"u{user}", "userType": user_type,
            "state": state, "commitId": sha, "submittedAt": f"2026-10-20T12:{minute:02d}:00Z", "body": "",
            "permission": "write"}


def observe(review, head, reviews_, minute=0):
    scope = review["scope"]
    data = snapshot()
    data.update(project=scope["project"], workspace=scope["workspace"], prNumber=7, reviews=reviews_,
                configuredRepository="owner/repo", configuredBaseBranch="main",
                observedAt=f"2026-10-20T13:{minute:02d}:00Z")
    data["repository"]["fullName"] = "Owner/Repo"
    data["pr"].update(number=7, headSha=head)
    db = review["service"].db_for(scope["project"])
    with db:
        db.execute("BEGIN IMMEDIATE")
        ReviewEvidenceRepository(db, scope["project"], scope["workspace"]).insert(data)


def gate(review, config=CONFIG):
    [item] = read_review_gates(review["service"], **review["scope"], config=config)
    return item["reviewGate"]


@pytest.fixture(name="sensitive")
def sensitive_fixture(review):  # noqa: F811
    review["reader"].files = SENSITIVE
    review["jobs"].sync(**review["scope"])
    return review


def test_gate_waits_for_review_then_for_a_human_approval_at_head(sensitive):
    review = sensitive
    assert read_review_gates(review["service"], **review["scope"], config={**CONFIG, "enabled": False}) is None
    assert gate(review) == {"status": "pending", "openImportant": 0, "requiredHumanApprovals": 1,
                            "humanApprovalsAtHead": 0,
                            "reasons": ["review_in_progress", "human_approvals_missing", "github_evidence_missing"]}
    run_finders(review, *[{"findings": []}] * 3)
    observe(review, SHA, [approval()])
    assert gate(review) == {"status": "ready", "openImportant": 0, "requiredHumanApprovals": 1,
                            "humanApprovalsAtHead": 1, "reasons": []}
    observe(review, SHA, [approval(), approval(user=3, state="CHANGES_REQUESTED", minute=5)], minute=10)
    assert gate(review)["status"] == "blocked" and gate(review)["reasons"] == ["changes_requested"]


def test_stale_approval_from_an_older_head_is_not_counted(sensitive):
    review = sensitive
    run_finders(review, *[{"findings": []}] * 3)
    observe(review, SHA, [approval()])
    push(review, NEXT_SHA, "push")
    observe(review, NEXT_SHA, [approval(sha=SHA)], minute=20)  # Approval of the old commit on the new head.
    result = gate(review)
    assert result["humanApprovalsAtHead"] == 0 and result["status"] == "pending"
    assert result["reasons"] == ["review_not_enqueued", "human_approvals_missing"]
    review["jobs"].sync(**review["scope"])
    run_finders(review, *[{"findings": []}] * 3)
    observe(review, SHA, [approval()], minute=30)  # Newest snapshot is for the old head only.
    assert gate(review)["humanApprovalsAtHead"] == 0


def test_agent_approvals_never_count(sensitive):
    review = sensitive
    run_finders(review, *[{"findings": []}] * 3)
    observe(review, SHA, [approval(user=5, user_type="Bot"), approval(user=6)])
    assert gate(review)["humanApprovalsAtHead"] == 1
    assert gate(review, {**CONFIG, "agentAccountIds": [6]})["humanApprovalsAtHead"] == 0


def test_open_important_finding_blocks_until_resolved_by_a_human(sensitive):
    review = sensitive
    run_finders(review, *[{"findings": [found("fp-aaaaaaaa")]}] * 3)
    run_voters(review, [{"fp-aaaaaaaa": "confirm"}] * 3)
    observe(review, SHA, [approval()])
    result = gate(review)
    assert result["status"] == "blocked" and result["openImportant"] == 1 and result["reasons"] == ["open_important_findings"]
    finding = review["jobs"].list(**review["scope"])["findings"][0]["findingId"]
    review["findings"].resolve(finding, {**review["scope"], "reason": "Accepted risk."}, "human")
    assert gate(review)["status"] == "ready"


def test_agent_state_review_stage_claim_action_and_gap(sensitive):
    review = sensitive
    reviews.register(CONFIG)
    try:
        document = AgentState(review["service"]).read(**review["scope"])
    finally:
        reviews.register(None)
    stage = next(item for item in document["stages"] if item["id"] == "review")
    assert stage == {"id": "review", "count": 1, "health": "waiting", "reason": "review_gate_pending"}
    [action] = [item for item in document["actions"] if item["verb"] == "review.claim"]
    assert action["path"] == "/api/oporahub/review-jobs/claim" and action["status"] == "ready"
    assert action["preconditions"] == {"role": "finder", "headSha": SHA}
    assert "ai_review" not in [gap["id"] for gap in document["gaps"]]
    reviews.register({**CONFIG, "enabled": False})
    try:
        disabled = AgentState(review["service"]).read(**review["scope"])
    finally:
        reviews.register(None)
    assert "ai_review" in [gap["id"] for gap in disabled["gaps"]]
    assert not [item for item in disabled["actions"] if item["verb"] == "review.claim"]


def test_unobserved_change_fails_closed_to_two_approvals(review):  # noqa: F811
    class Broken:
        def change(self, *_):
            raise OSError("network down")

    review["jobs"]._reader = Broken()
    review["jobs"].sync(**review["scope"])
    assert gate(review)["requiredHumanApprovals"] == 2
    assert review["jobs"].list(**review["scope"])["jobs"][0]["risk"]["reasons"] == ["change_unobserved"]


def test_agent_state_with_review_jobs_stays_write_free(sensitive):
    """With review jobs enabled and a real PR link, the document is still built from SELECTs only."""
    review = sensitive
    db = review["service"].db_for(review["scope"]["project"])
    sql = []
    reviews.register(CONFIG)
    db.set_trace_callback(sql.append)
    try:
        AgentState(review["service"]).read(**review["scope"])
        read_review_gates(review["service"], **review["scope"], config=CONFIG)
    finally:
        db.set_trace_callback(None)
        reviews.register(None)
    assert not any(command.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN", "CREATE"))
                   for command in sql)
