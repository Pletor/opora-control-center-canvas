"""Review metrics math over seeded jobs, findings, evidence, decisions, reverts and incidents."""
from datetime import UTC, datetime

import pytest

from backend.canvas.opora_review_insight_common import writing
from backend.canvas.opora_review_metrics import read_review_metrics, window_seconds
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_jobs import CONFIG
from backend.canvas.test_opora_review_status import snapshot
from database.repositories.opora_review_evidence import ReviewEvidenceRepository
from database.repositories.opora_review_jobs import ReviewJobs

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC).timestamp()


def iso(hours_ago):
    return datetime.fromtimestamp(NOW - hours_ago * 3600, UTC).isoformat(timespec="microseconds")


def head(number, round_):
    return f"{number:02d}{round_:02d}".ljust(40, "a")


def seed_pr(service, scope, number, *, rounds=1, started=10, findings=(), rejected=0, open_round=False):
    """`findings` = [(fingerprint, severity, status)]; rounds are completed jobs, one hour apart."""
    project, workspace = scope["project"], scope["workspace"]
    with writing(service, project) as (db, _):
        store = ReviewJobs(db, project, workspace)
        for index in range(1, rounds + 1 + open_round):
            done = index <= rounds
            candidates = [{"kind": "finding", "fingerprint": f"x:rej{n}", "accepted": False} for n in range(rejected)
                          ] if index == 1 else []
            store.insert_job({
                "job_id": f"rj_{number}_{index}", "execution_id": f"e{number}", "node_id": "card",
                "repository": "owner/repo", "number": number, "base_sha": "b" * 40, "head_sha": head(number, index),
                "round": index, "since_sha": None, "risk_tier": "low", "risk": {}, "required_approvals": 0,
                "finders": 3, "voters": 3, "required_votes": 2, "phase": "completed" if done else "find",
                "candidates": candidates, "created_at": iso(started - index + 1), "updated_at": iso(started),
                "completed_at": iso(started) if done else None})
        for fingerprint, severity, status in findings:
            store.insert_finding({
                "finding_id": f"rf_{number}_{fingerprint}", "repository": "owner/repo", "number": number,
                "fingerprint": fingerprint, "job_id": f"rj_{number}_1", "round": 1, "head_sha": head(number, 1),
                "severity": severity, "status": status, "content": {"path": "a.py", "line": 1, "title": fingerprint},
                "resolution": None, "created_at": iso(started), "updated_at": iso(started)})


def evidence(service, scope, number, reviews, observed="2026-10-21T11:00:00Z"):
    data = snapshot()
    data.update(project=scope["project"], workspace=scope["workspace"], prNumber=number, reviews=reviews,
                configuredRepository="owner/repo", configuredBaseBranch="main", observedAt=observed)
    data["pr"].update(number=number, headSha=head(number, 1))
    db = service.db_for(scope["project"])
    with db:
        db.execute("BEGIN IMMEDIATE")
        ReviewEvidenceRepository(db, scope["project"], scope["workspace"]).insert(data)


def review(user, state, submitted, number):
    return {"id": user * 100 + number, "userId": user, "login": f"u{user}", "userType": "User", "state": state,
            "commitId": head(number, 1), "submittedAt": submitted, "body": "", "permission": "write"}


def test_window_validation():
    assert window_seconds("all") is None and window_seconds("7d") == 7 * 86400
    for bad in ("0d", "7", "7w", "1000d", 7):
        with pytest.raises(ValueError):
            window_seconds(bad)


def test_metrics_math_is_deterministic(world):  # noqa: F811
    service, scope, _ = world
    # PR 1: two rounds, one important fixed, one nit resolved without fix, one rejected candidate, two approvals.
    seed_pr(service, scope, 1, rounds=2, started=10, rejected=1,
            findings=[("a.py:null:x", "important", "fixed"), ("a.py:style:y", "nit", "resolved")])
    # PR 2: one round, one open pre_existing finding, one approval, a revert and an incident.
    seed_pr(service, scope, 2, rounds=1, started=20, findings=[("b.py:old:z", "pre_existing", "open")])
    # PR 3: started 40 days ago, outside a 30d window.
    seed_pr(service, scope, 3, rounds=3, started=40 * 24, findings=[("c.py:null:q", "important", "fixed")])
    evidence(service, scope, 1, [review(2, "APPROVED", iso(7).replace("+00:00", "Z"), 1),
                                 review(3, "APPROVED", iso(5).replace("+00:00", "Z"), 1),
                                 review(99, "APPROVED", iso(9.5).replace("+00:00", "Z"), 1)])
    evidence(service, scope, 2, [review(2, "CHANGES_REQUESTED", iso(19).replace("+00:00", "Z"), 2)])
    with writing(service, scope["project"]) as (_, store):
        store.insert_revert("owner/repo", 2, 9, "f" * 40, iso(1))
        store.insert_incident(scope["workspace"], "ri_1", "owner/repo", 2, "INC-1", "Outage", "human", iso(1))
    metrics = read_review_metrics(service, scope["project"], window="30d", now=NOW,
                                  config={**CONFIG, "agentAccountIds": [99]})
    assert metrics["prsReviewed"] == 2
    assert metrics["findingsBySeverity"] == {"important": 1, "nit": 1, "pre_existing": 1}
    assert metrics["findingOutcomes"] == {"fixed": 1, "resolvedWithoutFix": 1, "rejectedByVoters": 1, "open": 1}
    assert metrics["findingAcceptanceRate"] == 0.5 and metrics["voterRejectionRate"] == 0.25
    assert metrics["roundsPerPr"] == {"mean": 1.5, "max": 2}
    assert metrics["humanApprovalsPerPr"] == 1.0  # PR1: 2 (agent 99 excluded), PR2: 0.
    # PR1 first job 10 h ago, first human decision 7 h ago → 3 h; PR2 job 20 h ago, decision 19 h ago → 1 h.
    assert metrics["timeToHumanDecisionSeconds"] == {"samples": 2, "median": 7200.0, "mean": 7200.0}
    assert metrics["guardrails"] == {"revertRate": 0.5, "incidentRate": 0.5}
    assert [item["reference"] for item in metrics["incidents"]] == ["INC-1"]
    assert [(row["number"], row["reverted"], row["humanApprovals"]) for row in metrics["prs"]] == [
        (1, False, 2), (2, True, 0)]
    everything = read_review_metrics(service, scope["project"], window="all", now=NOW, config=CONFIG)
    assert everything["prsReviewed"] == 3 and everything["roundsPerPr"] == {"mean": 2.0, "max": 3}
    assert read_review_metrics(service, scope["project"], window="30d", now=NOW, config=CONFIG) == \
        read_review_metrics(service, scope["project"], window="30d", now=NOW, config=CONFIG)
    empty = read_review_metrics(service, scope["project"], window="1d", now=NOW + 90 * 86400, config=CONFIG)
    assert empty["prsReviewed"] == 0 and empty["findingAcceptanceRate"] is None and empty["guardrails"] == {
        "revertRate": None, "incidentRate": None}
