"""Review events bind exact proposals; CAS and explicit human acknowledgement never write a plan."""
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_proposal_review_context import (
    anchor_exists,
    evaluate,
    proposal,
    read_only,
    require_writable,
)
from backend.canvas.opora_proposal_risk import classify_risk
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_proposal_reviews import (
    AcceptancePolicies,
    AcceptanceReceipts,
    ProposalReview,
)


class ProposalReviews:
    def __init__(self, canvas):
        self.canvas = canvas

    def context(self, project, workspace, kind, identifier):
        scope({"project": project, "workspace": workspace})
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                value = evaluate(db, project, workspace, kind, identifier)
                readonly = read_only(self.canvas, project, workspace)
                if readonly:
                    value["blockedReasons"].append("Workspace is read-only or no longer active.")
                    value["eligible"] = False
                return {**value, "readOnly": readonly}

    def policy(self, project, workspace):
        scope({"project": project, "workspace": workspace})
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            repo = AcceptancePolicies(db, project, workspace)
            head = repo.head()
            return {"policyHead": head, "policy": repo.read(head) if head else None,
                    "readOnly": read_only(self.canvas, project, workspace),
                    "acceptedHead": ChangesetRepository(db, project, workspace).head(),
                    "bootstrapException": "Initial specification baseline only; no accepted history or bootstrap receipt may exist."}

    def configure(self, payload, by):
        if set(payload) != {"project", "workspace", "expectedPolicyHead", "enabled", "rules"}:
            raise ValueError("Invalid acceptance policy fields.")
        author = _author(by, allow_agent=True)
        if author["kind"] != "human":
            raise ValueError("Only a human may configure acceptance policy.")
        project, workspace = scope(payload)
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                require_writable(self.canvas, project, workspace)
                return AcceptancePolicies(db, project, workspace).configure({"schemaVersion": 1,
                    "kind": "acceptance-policy", "project": project, "workspace": workspace,
                    "by": author, "createdAt": stamp(), "parentPolicyRevision": payload["expectedPolicyHead"],
                    "enabled": payload["enabled"], "rules": payload["rules"]}, payload["expectedPolicyHead"])

    def append(self, payload, by):
        if set(payload) != {"project", "workspace", "proposalKind", "proposalId", "expectedReviewHead", "idempotencyKey", "body"}:
            raise ValueError("Invalid proposal review event fields.")
        project, workspace = scope(payload)
        author = _author(by, allow_agent=True)
        body = payload["body"]
        if not isinstance(body, dict) or body.get("type") not in {"comment", "finding", "resolve", "ack"}:
            raise ValueError("Unsupported proposal review event body.")
        if body["type"] in {"resolve", "ack"} and author["kind"] != "human":
            raise ValueError("Only a human may resolve findings or acknowledge risk.")
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                require_writable(self.canvas, project, workspace)
                kind, identifier = payload["proposalKind"], payload["proposalId"]
                native = proposal(db, project, workspace, kind, identifier)
                risk = classify_risk(kind, native)
                fields = {"comment": {"type", "message", "anchor"}, "finding": {"type", "message", "anchor", "severity"},
                          "resolve": {"type", "targetEventId", "resolution", "reason"},
                          "ack": {"type", "policyId", "riskDigest", "parentAcceptedHead"}}
                if set(body) != fields[body["type"]]:
                    raise ValueError("Invalid typed proposal review event fields.")
                event = {"schemaVersion": 1, "kind": "proposal-review-event", "project": project,
                    "workspace": workspace, "proposalKind": kind, "proposalId": identifier,
                    "by": author, "createdAt": stamp(), "parentReviewEvent": payload["expectedReviewHead"],
                    "idempotencyKey": payload["idempotencyKey"], **body}
                if body["type"] == "ack":
                    event.update(risk=risk["level"], reviewHead=payload["expectedReviewHead"])
                repo = ProposalReview(db, project, workspace, kind, identifier)
                if repo.replay(payload["idempotencyKey"]) is not None:
                    return repo.append(event, payload["expectedReviewHead"])
                current = evaluate(db, project, workspace, kind, identifier)
                if body["type"] in {"comment", "finding"}:
                    anchor_exists(native, body["anchor"])
                elif body["type"] == "resolve":
                    if body["targetEventId"] not in {item["id"] for item in current["openFindings"]}:
                        raise ValueError("Resolution requires an open finding on this exact proposal.")
                elif (not current["policy"] or not current["policy"]["enabled"] or body["policyId"] != current["policyHead"]
                      or body["riskDigest"] != risk["digest"] or body["parentAcceptedHead"] != current["acceptedHead"]
                      or native["parentRevision"] != current["acceptedHead"]):
                    raise ValueError("Acknowledgement policy, risk or accepted parent changed.")
                return repo.append(event, payload["expectedReviewHead"])

    def receipt(self, project, workspace, revision):
        scope({"project": project, "workspace": workspace})
        with self.canvas.lock_for(project):
            from database.repositories.opora_changesets import ChangesetRepository
            db = self.canvas.db_for(project)
            ChangesetRepository(db, project, workspace).read(revision)
            return {"receipt": AcceptanceReceipts(db, project, workspace).read(revision)}
