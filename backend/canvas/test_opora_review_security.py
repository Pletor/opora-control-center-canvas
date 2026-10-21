"""Security review job kind: enqueue rules, same claim/vote contract, blocking and automatic clear."""
import pytest

from backend.canvas.opora_review_findings import HumanRequired
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import (
    config,
    gate_item,
    run_round,
    take_any,
    use,
)
from backend.canvas.test_opora_review_jobs import found, push
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

SECURITY = config(security={"min_tier": "high", "paths": ["**/auth/**"]})
AUTH = (("src/auth/login.py", 4, 1),)
LEAK = "src/auth/login.py:token-leak:login"


def jobs_by_kind(review):  # noqa: F811
    return {(job["kind"], job["headSha"]): job for job in review["jobs"].list(**review["scope"])["jobs"]}


def test_security_job_only_for_sensitive_risky_or_still_insecure_heads(review):  # noqa: F811
    use(review, SECURITY)
    [code] = review["jobs"].sync(**review["scope"])  # src/app.py, low tier: decided once, not required
    jobs = jobs_by_kind(review)
    assert jobs[("code", SHA)]["reviewJobId"] == code
    assert jobs[("security", SHA)]["phase"] == "not_required" and jobs[("security", SHA)]["risk"]["securityReasons"] == []
    assert review["jobs"].sync(**review["scope"]) == [] and len(review["reader"].calls) == 1
    assert "security_review_not_enqueued" not in gate_item(review)["reviewGate"]["reasons"]
    review["reader"].files = AUTH
    push(review, NEXT_SHA, "push")
    created = review["jobs"].sync(**review["scope"])
    security = jobs_by_kind(review)[("security", NEXT_SHA)]
    assert security["reviewJobId"] in created and security["phase"] == "find"
    assert security["risk"]["securityReasons"] == ["security_path:**/auth/**"]
    assert security["reviewJobId"] != jobs_by_kind(review)[("code", NEXT_SHA)]["reviewJobId"]
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "pending" and "security_review_in_progress" in item["reviewGate"]["reasons"]
    assert item["mergeReadiness"]["security"]["reviewJobId"] == security["reviewJobId"]


def test_risk_tier_and_unobserved_change_require_security_review(review):  # noqa: F811
    use(review, config(security={"min_tier": "medium"}))
    review["reader"].files = ((".github/workflows/ci.yml", 1, 0),)  # sensitive → medium tier
    review["jobs"].sync(**review["scope"])
    assert jobs_by_kind(review)[("security", SHA)]["risk"]["securityReasons"] == [
        "risk_tier:medium", "security_path:.github/workflows/**"]

    class Broken:
        def change(self, *_):
            raise OSError("down")

    review["jobs"]._reader = Broken()
    push(review, NEXT_SHA, "push")
    review["jobs"].sync(**review["scope"])
    assert jobs_by_kind(review)[("security", NEXT_SHA)]["risk"]["securityReasons"] == ["risk_tier:high"]


def test_workers_claim_security_slots_with_the_same_contract_and_see_the_kind(review):  # noqa: F811
    use(review, SECURITY)
    review["reader"].files = AUTH
    review["jobs"].sync(**review["scope"])
    kinds = []
    while (task := take_any(review, "finder")) is not None:
        kinds.append(task["job"]["kind"])
        assert set(task) >= {"token", "epoch", "knownFindings"} and task["job"]["headSha"] == SHA
    assert sorted(kinds) == ["code", "code", "security", "security"]


def test_open_security_finding_blocks_and_a_confirmed_fix_on_a_later_head_clears_it(review):  # noqa: F811
    use(review, SECURITY)
    review["reader"].files = AUTH
    review["jobs"].sync(**review["scope"])
    run_round(review, {"security": {"findings": [found(LEAK, path="src/auth/login.py")]}},
              {"security": {LEAK: "confirm"}})
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "blocked"
    assert {"open_security_findings", "open_important_findings"} <= set(item["reviewGate"]["reasons"])
    assert item["mergeReadiness"]["security"]["openImportant"] == 1
    [finding] = review["jobs"].list(**review["scope"])["findings"]
    # The fix lands in a small, non-sensitive commit: the open finding alone requires another security round.
    review["reader"].files = (("src/app.py", 2, 1),)
    push(review, NEXT_SHA, "push")
    review["jobs"].sync(**review["scope"])
    again = jobs_by_kind(review)[("security", NEXT_SHA)]
    assert again["risk"]["securityReasons"] == ["open_security_findings"]
    assert (again["round"], again["sinceSha"]) == (2, SHA)
    fixed = {"findings": [], "fixed": [{"findingId": finding["findingId"], "rationale": "Token no longer logged."}]}
    run_round(review, {"security": fixed}, {"security": {finding["findingId"]: "confirm"}})
    [after] = review["jobs"].list(**review["scope"])["findings"]
    assert after["status"] == "fixed" and after["resolution"]["headSha"] == NEXT_SHA
    assert gate_item(review)["reviewGate"] == {"status": "ready", "openImportant": 0, "requiredHumanApprovals": 0,
                                               "humanApprovalsAtHead": 0, "reasons": []}


def test_only_a_human_resolves_an_important_security_finding_without_a_fix(review):  # noqa: F811
    use(review, SECURITY)
    review["reader"].files = AUTH
    review["jobs"].sync(**review["scope"])
    run_round(review, {"security": {"findings": [found(LEAK, path="src/auth/login.py")]}},
              {"security": {LEAK: "confirm"}})
    [finding] = review["jobs"].list(**review["scope"])["findings"]
    with pytest.raises(HumanRequired):
        review["findings"].resolve(finding["findingId"], {**review["scope"], "reason": "Fine."}, "agent")
    review["findings"].resolve(finding["findingId"], {**review["scope"], "reason": "Test fixture key."}, "human")
    assert "open_security_findings" not in gate_item(review)["reviewGate"]["reasons"]


def test_disabled_security_rule_creates_no_security_jobs(review):  # noqa: F811
    use(review, config())
    review["reader"].files = AUTH
    review["jobs"].sync(**review["scope"])
    assert {job["kind"] for job in review["jobs"].list(**review["scope"])["jobs"]} == {"code"}
    assert gate_item(review)["mergeReadiness"]["security"] is None
