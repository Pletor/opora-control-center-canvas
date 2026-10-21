"""Distinct verified humans behind the approvals of one PR head (docs/oporahub-review-identity.md).

"An agent's approval never counts as a person's." Once the project has at least one verified
reviewer identity, the merge gate counts people, not accounts:

- a GitHub approval at the exact head counts only when its numeric account is linked to a
  verified identity (bots, PR author and configured agent accounts are never eligible);
- the Canvas operator who accepted the plan revision the execution ran under counts as one
  reviewer (the person directing the agent), once even when they also approved on GitHub;
- approvals from unverified accounts are reported, never counted.

Without any verified identity this returns None and the gate keeps counting accounts."""
from backend.canvas.opora_review_status import _reviews
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_review_insights import ReviewInsights


def approvers(evidence, repository, number, head, agent_ids):
    """Account IDs approving exactly `head` in the newest complete snapshot of that head."""
    for snapshot in evidence or []:
        if (snapshot.get("prNumber") != number
                or str((snapshot.get("repository") or {}).get("fullName", "")).casefold() != repository
                or snapshot.get("complete") is not True or (snapshot.get("pr") or {}).get("headSha") != head):
            continue
        reviews, invalid = _reviews(snapshot, head)
        if invalid:
            return set()
        return {review["userId"] for review in reviews if review["state"] == "APPROVED"
                and review["commitId"] == head and review["userId"] not in agent_ids}
    return set()


def director(db, project, workspace, accepted_revision, identities):
    """The verified operator identity when a human accepted the plan revision of this execution."""
    operator = next((row for row in identities if row["operator"]), None)
    if operator is None or not accepted_revision:
        return None
    try:
        revision = ChangesetRepository(db, project, workspace).read(accepted_revision)
    except (ValueError, KeyError, TypeError):
        return None
    return operator["identity_id"] if (revision.get("by") or {}).get("kind") == "human" else None


def count(db, project, workspace, link, evidence, agent_ids):
    """`{mode, count, identityIds, directorId, unverifiedApprovals}` or None (registry not in use)."""
    identities = ReviewInsights(db, project).verified()
    if not identities:
        return None
    by_account = {row["github_user_id"]: row["identity_id"] for row in identities}
    accounts = approvers(evidence, link["repository"], link["number"], link["head_sha"], set(agent_ids))
    people = {by_account[account] for account in accounts if account in by_account}
    lead = director(db, project, workspace, link.get("accepted_revision"), identities)
    if lead is not None:
        people.add(lead)
    return {"mode": "verified_humans", "count": len(people), "identityIds": sorted(people), "directorId": lead,
            "unverifiedApprovals": len(accounts - by_account.keys())}
