"""Human opt-in authority for durable read-only GitHub reconciliation."""
import time

from backend.canvas.authority import can_act
from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_hub_store import content_id
from backend.canvas.opora_reconciliation_projection import listing
from backend.canvas.opora_reconciliation_scope import candidate, historical_context, read_context
from backend.canvas.opora_review_policy import OporaReviewPolicy
from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs


class OporaReconciliation:
    def __init__(self, service):
        self.service = service

    def repository(self, project, workspace):
        return ReconciliationRepository(self.service.db_for(project), project, workspace)

    def list(self, project, workspace, actor="unknown"):
        return listing(self.service, project, workspace, actor)

    def candidate(self, project, workspace, evidence_id, actor="unknown"):
        identifier(evidence_id)
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            current, binding = candidate(self.service, project, workspace, evidence_id)
            existing = self.repository(project, workspace).enabled_for(binding["repository"]["id"], binding["pr"]["id"])
            return {"project": project, "workspace": workspace, "evidenceId": evidence_id, "binding": binding,
                    "currentAcceptedHead": current["acceptedHead"], "existingEnabledBinding": existing,
                    "canConfigure": can_act(actor) and existing is None,
                    "unavailableReason": "Pause the existing subscription first." if existing else
                    (None if can_act(actor) else "Human UI session required.")}

    def enroll(self, payload, by):
        project, workspace = validate(payload, {"expectedAcceptedHead", "identityEvidenceId", "requestId"})
        identifier(payload["expectedAcceptedHead"])
        identifier(payload["identityEvidenceId"])
        author = OporaReviewPolicy.author(by)
        digest = content_id({"action": "enroll", "payload": payload, "by": author})
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            jobs = ReconciliationJobs(repo.db, project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                replay = repo.replay(payload["requestId"], digest)
                if replay:
                    return replay
                current, pin = candidate(self.service, project, workspace, payload["identityEvidenceId"])
                if current["acceptedHead"] != payload["expectedAcceptedHead"]:
                    raise ValueError("Accepted revision changed; refresh before enrollment.")
                if repo.enabled_for(pin["repository"]["id"], pin["pr"]["id"]):
                    raise ValueError("Pause the existing subscription for this PR first.")
                binding = repo.insert("binding", {"schemaVersion": 1, "project": project, "workspace": workspace,
                                                 **pin, "by": author, "createdAt": stamp()})
                control = self._control(repo, binding, None, "enroll", True, payload, digest, author)
                result = {"binding": binding, "control": control, "job": jobs.create(binding, control, time.time())}
                repo.remember(payload["requestId"], digest, result)
                return result

    @staticmethod
    def _control(repo, binding, previous, action, enabled, payload, digest, author):
        return repo.activate_control({"schemaVersion": 1, "project": binding["project"], "workspace": binding["workspace"],
                                      "bindingId": binding["id"], "parentControlId": previous["id"] if previous else None,
                                      "generation": previous["generation"] + 1 if previous else 1,
                                      "action": action, "enabled": enabled, "requestId": payload["requestId"],
                                      "requestDigest": digest, "by": author, "createdAt": stamp()},
                                     previous["generation"] if previous else 0)

    def control(self, binding_id, payload, by):
        project, workspace = validate(payload, {"expectedGeneration", "action", "requestId"})
        identifier(binding_id)
        if type(payload["expectedGeneration"]) is not int or payload["expectedGeneration"] < 1:
            raise ValueError("Invalid expected subscription generation.")
        if not isinstance(payload["action"], str) or payload["action"] not in {"pause", "resume", "retry"}:
            raise ValueError("Unknown subscription control.")
        author = OporaReviewPolicy.author(by)
        digest = content_id({"bindingId": binding_id, "payload": payload, "by": author})
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = self.repository(project, workspace)
            jobs = ReconciliationJobs(repo.db, project, workspace)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                replay = repo.replay(payload["requestId"], digest)
                if replay:
                    return replay
                binding = repo.read("binding", binding_id)
                previous = repo.latest_control(binding_id)
                if previous["generation"] != payload["expectedGeneration"]:
                    raise ValueError("Subscription generation changed; refresh before controlling.")
                action = payload["action"]
                if action != "pause":
                    historical_context(self.service, project, workspace, binding)
                    if repo.enabled_for(binding["repository"]["id"], binding["pr"]["id"], exclude=binding_id):
                        raise ValueError("Pause the existing subscription for this PR first.")
                    if action == "retry" and not previous["enabled"]:
                        raise ValueError("Resume the paused subscription before retrying.")
                control = self._control(repo, binding, previous, action, action != "pause", payload, digest, author)
                result = {"binding": binding, "control": control, "job": jobs.control(binding_id, control, time.time())}
                repo.remember(payload["requestId"], digest, result)
                return result

    def history(self, project, workspace, binding_id, cursor=None, attempt_cursor=None):
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            read_context(self.service, project, workspace)
            repo = self.repository(project, workspace)
            try:
                position = 0 if cursor is None else int(cursor)
                attempt_position = 0 if attempt_cursor is None else int(attempt_cursor)
            except (TypeError, ValueError):
                raise ValueError("Invalid reconciliation history cursor.") from None
            binding = repo.read("binding", binding_id)
            attempts = ReconciliationJobs(repo.db, project, workspace).attempt_history(binding_id, cursor=attempt_position)
            return {"binding": binding, **repo.history(binding_id, position),
                    "attempts": attempts["items"], "nextAttemptCursor": attempts["nextCursor"]}
