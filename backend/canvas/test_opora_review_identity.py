"""Reviewer identity registry: claim → GitHub-observed proof → verified; distinct-human gate counting."""
import pytest

from backend.canvas.opora_review_gate import read_review_gates
from backend.canvas.opora_review_identity import IdentityProofMissing, ReviewIdentities
from backend.canvas.opora_review_insight_common import InsightHumanRequired, InsightMissing
from backend.canvas.test_opora_execution_pull_requests import SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate import approval, observe
from backend.canvas.test_opora_review_jobs import CONFIG, run_finders
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401


class Comments:
    def __init__(self):
        self.items, self.calls = [], []

    def comments(self, repository, number):
        self.calls.append((repository, number))
        return list(self.items)

    def post(self, user_id, login, body, user_type="User"):
        self.items.append({"id": 900 + len(self.items), "login": login, "userId": user_id, "userType": user_type,
                           "body": body, "createdAt": "2026-10-21T10:00:00Z", "url": "https://github.com/x"})


def registry(service, agent_ids=(99,)):
    reader = Comments()
    return ReviewIdentities(service, reader, agent_ids=set(agent_ids)), reader


def enroll(identities, reader, project, user_id, login, operator=False):
    claimed = identities.claim({"project": project, "name": login.title(), "githubLogin": login,
                                "operator": operator}, "human")
    reader.post(user_id, login, "Ahoj\n" + claimed["marker"] + "\n")
    return identities.verify(claimed["identityId"], {"project": project, "number": 3}, "human")


def test_claim_and_verify_flow_requires_human_and_a_matching_github_comment(world):  # noqa: F811
    service, scope, _ = world
    project = scope["project"]
    identities, reader = registry(service)
    claim = {"project": project, "name": "Martin", "githubLogin": "Martin-H", "operator": True}
    with pytest.raises(InsightHumanRequired):
        identities.claim(claim, "agent")
    first = identities.claim(claim, "human")
    assert first["state"] == "claimed" and first["githubLogin"] == "martin-h" and first["operator"] is True
    assert first["marker"] == f"Opora-Identity: {first['identityId']} " + first["marker"].split()[-1]
    assert identities.claim(claim, "human")["marker"] == first["marker"]  # Idempotent: same nonce.
    [listed] = identities.list(project, "agent")["items"]
    assert "marker" not in listed and listed["githubUserId"] is None
    verify = {"project": project, "number": 3}
    with pytest.raises(InsightHumanRequired):
        identities.verify(first["identityId"], verify, "agent")
    with pytest.raises(InsightMissing):
        identities.verify("hi_missing", verify, "human")
    reader.post(7, "someone-else", first["marker"])           # Wrong account.
    reader.post(7, "martin-h", first["marker"], "Bot")        # Not a User.
    reader.post(99, "martin-h", first["marker"])               # Configured agent account.
    reader.post(7, "martin-h", "Opora-Identity: " + first["identityId"] + " deadbeef")  # Wrong nonce.
    with pytest.raises(IdentityProofMissing):
        identities.verify(first["identityId"], verify, "human")
    reader.post(7, "MARTIN-H", "Tady jsem:\n  " + first["marker"] + "  \n")
    verified = identities.verify(first["identityId"], verify, "human")
    assert verified["state"] == "verified" and verified["githubUserId"] == 7 and "marker" not in verified
    assert verified["evidence"]["repository"] == "owner/repo" and verified["evidence"]["commentId"] == 904
    assert reader.calls[-1] == ("owner/repo", 3)
    with pytest.raises(ValueError, match="už je ověřený"):
        identities.claim(claim, "human")
    with pytest.raises(ValueError, match="Ověřit lze jen"):
        identities.verify(first["identityId"], verify, "human")


def test_operator_is_unique_and_revoke_allows_a_fresh_claim(world):  # noqa: F811
    service, scope, _ = world
    project = scope["project"]
    identities, reader = registry(service)
    operator = enroll(identities, reader, project, 7, "martin", operator=True)
    with pytest.raises(ValueError, match="Operátor"):
        identities.claim({"project": project, "name": "B", "githubLogin": "bob", "operator": True}, "human")
    with pytest.raises(InsightHumanRequired):
        identities.revoke(operator["identityId"], {"project": project}, "agent")
    revoked = identities.revoke(operator["identityId"], {"project": project}, "human")
    assert revoked["state"] == "revoked"
    again = identities.claim({"project": project, "name": "Martin", "githubLogin": "martin", "operator": True},
                             "human")
    assert again["state"] == "claimed" and again["githubUserId"] is None and again["marker"] != operator.get("marker")
    with pytest.raises(ValueError):
        identities.claim({"project": project, "name": "X", "githubLogin": "bad[bot]"}, "human")


@pytest.fixture(name="high")
def high_fixture(review):  # noqa: F811
    review["reader"].files = (("src/app.py", 1000, 0),)  # High tier: two human approvals.
    review["jobs"].sync(**review["scope"])
    run_finders(review, *[{"findings": []}] * 3)
    return review


def gate(subject, config=CONFIG):
    [item] = read_review_gates(subject["service"], **subject["scope"], config=config)
    return item["reviewGate"]


def test_gate_counts_distinct_verified_humans_and_the_director_once(high):
    review = high  # noqa: F811
    project = review["scope"]["project"]
    observe(review, SHA, [approval(user=2), approval(user=3)])
    legacy = gate(review)
    assert legacy["status"] == "ready" and legacy["humanApprovalsAtHead"] == 2 and "humans" not in legacy
    identities, reader = registry(review["service"])
    operator = enroll(identities, reader, project, 2, "u2", operator=True)
    # Registry in use: account 3 is unverified, account 2 is the operator who also directed the run.
    counted = gate(review)
    assert counted["humanApprovalsAtHead"] == 1 and counted["status"] == "pending"
    assert counted["humans"] == {"mode": "verified_humans", "count": 1, "identityIds": [operator["identityId"]],
                                 "directorId": operator["identityId"], "unverifiedApprovals": 1}
    other = enroll(identities, reader, project, 3, "u3")
    assert gate(review)["humanApprovalsAtHead"] == 2 and gate(review)["status"] == "ready"
    observe(review, SHA, [approval(user=3)], minute=5)  # Director + one other verified person = two people.
    result = gate(review)
    assert result["humans"]["identityIds"] == sorted([operator["identityId"], other["identityId"]])
    assert result["status"] == "ready"
    # A verified account configured as an agent never counts; bots never count.
    assert gate(review, {**CONFIG, "agentAccountIds": [3]})["humanApprovalsAtHead"] == 1
    observe(review, SHA, [approval(user=3, user_type="Bot")], minute=10)
    assert gate(review)["humanApprovalsAtHead"] == 1
    identities.revoke(operator["identityId"], {"project": project}, "human")
    observe(review, SHA, [approval(user=2), approval(user=3)], minute=15)
    revoked = gate(review)  # Without a verified operator nobody directs: only u3 counts.
    assert revoked["humans"]["directorId"] is None and revoked["humanApprovalsAtHead"] == 1
