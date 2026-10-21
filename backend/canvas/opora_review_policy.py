"""Human-controlled local review policy, independent of plan acceptance and GitHub writes."""
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_review_policy_identity import pinned_repository
from backend.canvas.opora_review_policy_validation import rules
from backend.canvas.opora_review_scope import context
from database.repositories.opora_review_attempts import number
from database.repositories.opora_review_evidence import ReviewEvidenceRepository
from database.repositories.opora_review_policy import Policies


class OporaReviewPolicy:
    def __init__(self, service):
        self.service = service

    def repository(self, project, workspace):
        return Policies(self.service.db_for(project), project, workspace)

    def context(self, project, workspace, *, actor="unknown"):
        scope({"project": project, "workspace": workspace})
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            current = context(self.service, project, workspace)
            repo = self.repository(project, workspace)
            head = repo.head()
            reason = current["unavailableReason"] or ("Policy configuration requires a human UI session." if actor != "human" else None)
            return {"project": project, "workspace": workspace, "policyHead": head, "policy": repo.read(head) if head else None,
                    "canConfigure": actor == "human" and current["available"], "unavailableReason": reason,
                    "acceptedHead": current["acceptedHead"]}

    def history(self, project, workspace):
        scope({"project": project, "workspace": workspace})
        with self.service.lock_for(project):
            repo = self.repository(project, workspace)
            return {"policyHead": repo.head(), "items": repo.history()}

    @staticmethod
    def author(by):
        author = _author(by)
        if author["kind"] != "human":
            raise ValueError("Only a human may configure review policy.")
        return author

    def configure(self, payload, by):
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "expectedPolicyHead", "identityEvidenceId", "rules"}:
            raise ValueError("Policy configuration accepts only scope, expected head, evidence ID and rules.")
        project, workspace = scope(payload)
        expected, evidence_id = payload["expectedPolicyHead"], payload["identityEvidenceId"]
        identifier(expected, nullable=True)
        identifier(evidence_id)
        normalized, author = rules(payload["rules"]), self.author(by)
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                current = context(self.service, project, workspace)
                if not current["available"]:
                    raise ValueError(current["unavailableReason"])
                snapshot = ReviewEvidenceRepository(repo.db, project, workspace).read(evidence_id)
                repository = pinned_repository(snapshot, current)
                head = repo.head()
                if head != expected:
                    existing = repo.read(head) if head else None
                    if (existing and existing["parentPolicyRevision"] == expected and existing["enabled"]
                            and existing["identityEvidenceId"] == evidence_id and existing["rules"] == normalized
                            and existing["repository"] == repository and existing["by"] == author):
                        return {"policyHead": head, "policy": existing}
                    raise ValueError("Policy head changed; refresh before configuring policy.")
                record = repo.activate({"schemaVersion": 1, "kind": "review-policy", "project": project, "workspace": workspace,
                    "parentPolicyRevision": expected, "enabled": True, "repository": repository, "identityEvidenceId": evidence_id,
                    "rules": normalized, "by": author, "createdAt": stamp()}, expected)
                return {"policyHead": record["id"], "policy": record}

    def disable(self, payload, by):
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "expectedPolicyHead"}:
            raise ValueError("Invalid policy disable fields.")
        project, workspace = scope(payload)
        expected, author = payload["expectedPolicyHead"], self.author(by)
        identifier(expected)
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                if self.service.view(project, workspace)["readOnly"]:
                    raise ValueError("Workspace is read-only.")
                if repo.head() != expected:
                    raise ValueError("Policy head changed; refresh before disabling policy.")
                old = repo.read(expected)
                content = {key: value for key, value in old.items() if key != "id"}
                content.update(parentPolicyRevision=expected, enabled=False, by=author, createdAt=stamp())
                record = repo.activate(content, expected)
                return {"policyHead": record["id"], "policy": record}

    def status(self, project, workspace, pr_number):
        from backend.canvas.opora_review_policy_observation import policy_evaluation
        scope({"project": project, "workspace": workspace})
        number(pr_number)
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            current = context(self.service, project, workspace)
            return {"project": project, "workspace": workspace, "prNumber": pr_number,
                    "policyEvaluation": policy_evaluation(self.service, project, workspace, pr_number, current)}
