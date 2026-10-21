"""One transaction-local review guard and immutable evidence for existing acceptors."""
from backend.canvas.opora_proposal_review_context import evaluate
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_proposal_reviews import AcceptancePolicies, AcceptanceReceipts


def guard(db, project, workspace, kind, identifier):
    if not db.in_transaction:
        raise RuntimeError("Proposal acceptance review requires the caller transaction.")
    policies = AcceptancePolicies(db, project, workspace)
    policy_head = policies.head()
    if policy_head is None or not policies.read(policy_head)["enabled"]:
        return None
    current = evaluate(db, project, workspace, kind, identifier)
    if current["blockedReasons"]:
        raise ValueError(" ".join(current["blockedReasons"]))
    acknowledgement = current["acknowledgement"]
    return {"policyId": current["policyHead"], "proposalKind": kind, "proposalId": identifier,
            "risk": current["risk"]["level"], "reasons": current["risk"]["reasons"],
            "reviewHead": current["reviewHead"], "ackId": acknowledgement["id"] if acknowledgement else None,
            "bootstrap": False}


def bootstrap(db, project, workspace):
    if not db.in_transaction:
        raise RuntimeError("Bootstrap review requires the caller transaction.")
    policies = AcceptancePolicies(db, project, workspace)
    head = policies.head()
    if head is None or not policies.read(head)["enabled"]:
        return None
    if (ChangesetRepository(db, project, workspace).head() is not None
            or db.execute("SELECT 1 FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? LIMIT 1", (project, workspace)).fetchone()
            or db.execute("SELECT 1 FROM opora_acceptance_receipts WHERE project_id=? AND workspace_id=? LIMIT 1", (project, workspace)).fetchone()):
        raise ValueError("Bootstrap requires no accepted head, accepted history or prior acceptance receipt.")
    return {"policyId": head, "proposalKind": None, "proposalId": None, "risk": "critical",
            "reasons": ["Initial specification baseline is an explicit one-time bootstrap exception."],
            "reviewHead": None, "ackId": None, "bootstrap": True}


def seal(db, project, workspace, authorization, accepted):
    if authorization is None:
        return
    if not db.in_transaction:
        raise RuntimeError("Acceptance evidence requires the caller transaction.")
    AcceptanceReceipts(db, project, workspace).insert({"schemaVersion": 1, "kind": "acceptance-receipt",
        "project": project, "workspace": workspace, "by": accepted["by"], "createdAt": accepted["createdAt"],
        "acceptedRevision": accepted["id"], **authorization})
