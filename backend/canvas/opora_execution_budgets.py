"""Human-controlled per-card policy; family costs never reset on policy revisions."""

import time

from backend.canvas.authority import can_act
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_budget_legacy import seed_legacy
from backend.canvas.opora_execution_budget_scope import current
from backend.canvas.opora_execution_budget_status import status
from backend.canvas.opora_execution_budget_validation import limits, request_id
from backend.canvas.opora_hub_store import content_id
from backend.canvas.opora_review_policy import OporaReviewPolicy
from database.repositories.opora_execution_budgets import Budgets


class ExecutionBudgets:
    def __init__(self, service):
        self.service = service

    @staticmethod
    def fields(payload, extra):
        if not isinstance(payload, dict) or set(payload) != {
            "project",
            "workspace",
            "nodeId",
            *extra,
        }:
            raise ValueError("Invalid execution budget fields.")
        project, workspace = scope(payload)
        from backend.canvas.opora_execution_validation import validate

        validate({**{k: payload[k] for k in ("project", "workspace", "nodeId")}}, {"nodeId"})
        return project, workspace, payload["nodeId"]

    def context(self, project, workspace, nodeId, actor="unknown"):
        self.fields({"project": project, "workspace": workspace, "nodeId": nodeId}, set())
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            view = current(self.service, project, workspace, nodeId)
            value = status(
                self.service.db_for(project), project, workspace, nodeId, view["acceptedHead"]
            )
            return {
                "project": project,
                "workspace": workspace,
                "nodeId": nodeId,
                "acceptedHead": view["acceptedHead"],
                "canConfigure": can_act(actor) and view["available"],
                "canCancel": can_act(actor),
                "unavailableReason": view["unavailableReason"]
                or (None if can_act(actor) else "Human UI session required."),
                **value,
                "budget": value,
            }

    def configure(self, payload, by):
        project, workspace, node = self.fields(
            payload, {"expectedPolicyHead", "expectedAcceptedHead", "requestId", "limits"}
        )
        identifier(payload["expectedPolicyHead"], nullable=True)
        identifier(payload["expectedAcceptedHead"])
        request_id(payload["requestId"])
        normalized = limits(payload["limits"])
        author = OporaReviewPolicy.author(by)
        digest = content_id({"operation": "budget-policy", "payload": payload, "by": author})
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            repo = Budgets(self.service.db_for(project), project, workspace, node)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                replay = repo.replay(payload["requestId"], digest)
                if replay:
                    return replay
                view = current(self.service, project, workspace, node)
                if not view["available"]:
                    raise ValueError(view["unavailableReason"])
                if view["acceptedHead"] != payload["expectedAcceptedHead"]:
                    raise ValueError("Accepted revision changed before budget policy publication.")
                lease = repo.db.execute(
                    "SELECT expires_at FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=?",
                    (*repo.scope, node),
                ).fetchone()
                if lease and lease[0] > time.time() and not repo.enrolled():
                    raise ValueError(
                        "Release or wait for the active card lease before configuring its budget."
                    )
                if repo.head() != payload["expectedPolicyHead"]:
                    raise ValueError("Budget policy head changed; refresh context.")
                policy = repo.activate(
                    {
                        "schemaVersion": 1,
                        "project": project,
                        "workspace": workspace,
                        "nodeId": node,
                        "acceptedRevision": view["acceptedHead"],
                        "parentPolicyHead": payload["expectedPolicyHead"],
                        "limits": normalized,
                        "by": author,
                        "createdAt": stamp(),
                        "requestId": payload["requestId"],
                        "requestDigest": digest,
                    },
                    payload["expectedPolicyHead"],
                )
                seed_legacy(repo, view["acceptedHead"])
                result = {
                    "policyHead": policy["id"],
                    "policy": policy,
                    "family": repo.family(view["acceptedHead"]),
                }
                repo.remember(payload["requestId"], digest, result)
                return result

    def history(self, project, workspace, nodeId, actor="unknown"):
        self.fields({"project": project, "workspace": workspace, "nodeId": nodeId}, set())
        with self.service.graph_lock_for(project), self.service.lock_for(project):
            view = current(self.service, project, workspace, nodeId)
            repo = Budgets(self.service.db_for(project), project, workspace, nodeId)
            policies = repo.policies()
            rows = repo.db.execute(
                "SELECT content FROM opora_execution_budget_ledger WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY rowid DESC LIMIT 100",
                (*repo.scope, nodeId),
            ).fetchall()
            import json

            events = []
            families = {}
            for (raw,) in rows:
                candidate = json.loads(raw)
                accepted = candidate["acceptedRevision"]
                if accepted not in families:
                    families[accepted] = {item["id"]: item for item in repo.events(accepted)}
                events.append(families[accepted][candidate["id"]])
            cancels = repo.db.execute(
                "SELECT content FROM opora_execution_budget_cancels WHERE project_id=? AND workspace_id=? ORDER BY rowid DESC LIMIT 100",
                repo.scope,
            ).fetchall()
            from database.repositories.opora_execution_budget_receipts import cancellation

            cancellation_records = []
            for (raw,) in cancels:
                candidate = json.loads(raw)
                if not isinstance(candidate, dict):
                    raise ValueError("Malformed stored cancellation history.")  # noqa: TRY004 - domain error maps to HTTP409.
                if candidate.get("nodeId") == nodeId:
                    cancellation_records.append(cancellation(repo, candidate))
            return {
                "project": project,
                "workspace": workspace,
                "nodeId": nodeId,
                "acceptedHead": view["acceptedHead"],
                "policies": policies,
                "allocations": events,
                "cancellations": cancellation_records,
                "canCancel": can_act(actor),
                "nextCursor": None,
            }
