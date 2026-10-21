"""Native immutable proposal identity, anchored plain-text review and current policy gates."""
import re

from backend.canvas.opora_proposal_risk import classify_risk
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords
from database.repositories.opora_graph_changes import GraphChanges
from database.repositories.opora_proposal_reviews import (
    AcceptancePolicies,
    AcceptanceReceipts,
    ProposalReview,
)

LEVELS = {"standard": 0, "elevated": 1, "critical": 2, "none": 3}


def read_only(canvas, project, workspace):
    try:
        return workspace == "architecture" or canvas.view(project, workspace)["readOnly"]
    except ValueError:
        return True  # Existing immutable history can remain inspectable, never writable.


def require_writable(canvas, project, workspace):
    if read_only(canvas, project, workspace):
        raise ValueError("Proposal review requires an existing writable workspace.")


def proposal(db, project, workspace, kind, identifier):
    if kind == "spec":
        value = ChangesetRepository(db, project, workspace).read(identifier, proposal=True)
        if "kind" in value:
            raise ValueError("Wrong native specification proposal kind.")
    elif kind == "content":
        value = ContentRecords(db, project, workspace).read(identifier)
    elif kind in {"graph-addition", "graph-change"}:
        value = GraphChanges(db, project, workspace).read(identifier)
    else:
        raise ValueError("Unsupported proposal review kind.")
    classify_risk(kind, value)  # Also checks the native discriminator and typed risk inputs.
    return value


def anchor_exists(value, pointer):
    if not isinstance(pointer, str) or len(pointer) > 2000 or (pointer and not pointer.startswith("/")):
        raise ValueError("Review anchor must be an RFC6901 JSON pointer.")
    if not pointer:
        return
    for raw in pointer.split("/")[1:]:
        if re.search(r"~(?![01])", raw):
            raise ValueError("Invalid review pointer escape.")
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and int(key) < len(value):
            value = value[int(key)]
        else:
            raise ValueError("Review anchor does not exist in this immutable proposal.")


def evaluate(db, project, workspace, kind, identifier):
    native = proposal(db, project, workspace, kind, identifier)
    risk = classify_risk(kind, native)
    policies = AcceptancePolicies(db, project, workspace)
    policy_id = policies.head()
    policy = policies.read(policy_id) if policy_id else None
    reviews = ProposalReview(db, project, workspace, kind, identifier)
    events = reviews.events()
    resolved = {event["targetEventId"] for event in events if event["type"] == "resolve"}
    findings = [event for event in events if event["type"] == "finding" and event["id"] not in resolved]
    head = ChangesetRepository(db, project, workspace).head()
    latest = events[-1] if events else None
    acknowledgement = latest if (latest and latest["type"] == "ack" and latest["policyId"] == policy_id
        and latest["parentAcceptedHead"] == head == native["parentRevision"]
        and latest["riskDigest"] == risk["digest"] and latest["reviewHead"] == latest["parentReviewEvent"]) else None
    enabled = bool(policy and policy["enabled"])
    required = enabled and LEVELS[risk["level"]] >= LEVELS[policy["rules"]["requireAcknowledgementFrom"]]
    reasons = []
    if native["parentRevision"] != head:
        reasons.append("Proposal has a stale accepted parent; rebase it explicitly.")
    if enabled and policy["rules"]["blockOpenFindings"] and any(item["severity"] == "blocking" for item in findings):
        reasons.append("Open blocking findings require a human resolution.")
    if required and acknowledgement is None:
        reasons.append("Current human acknowledgement of this proposal, policy and review head is required.")
    accepted = db.execute("SELECT id FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? AND proposal_id=?",
                          (project, workspace, identifier)).fetchone()
    accepted_id = ChangesetRepository(db, project, workspace).read(accepted[0])["id"] if accepted else None
    return {"proposalKind": kind, "proposalId": identifier, "parentAcceptedHead": native["parentRevision"],
            "acceptedRevision": accepted_id,
            "receipt": AcceptanceReceipts(db, project, workspace).read(accepted_id) if accepted_id else None,
            "acceptedHead": head, "risk": risk, "policyHead": policy_id, "policy": policy,
            "reviewHead": reviews.head(), "events": events, "openFindings": findings,
            "acknowledgement": acknowledgement, "acknowledgementRequired": bool(required),
            "blockedReasons": reasons, "eligible": not reasons,
            "identityPolicy": "Local names do not prove independent human votes."}
