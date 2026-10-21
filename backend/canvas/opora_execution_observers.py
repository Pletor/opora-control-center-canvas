"""Canvas verifies execution authority; independent brokers attest provider readbacks."""
import time

from backend.canvas.canvas_service import now
from backend.canvas.graph import digest
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_execution_observer_auth import observers
from backend.canvas.opora_execution_observer_validation import intent, observation
from backend.canvas.opora_executions import OporaExecutions
from database.repositories import opora_execution_observer_sessions as sessions
from database.repositories.opora_execution_observers import ObserverRecords


class ExecutionObservers:
    def __init__(self, canvas):
        self.canvas = canvas
        self.executions = OporaExecutions(canvas)

    def _binding(self, execution, payload):
        assignment = execution.get("assignment", {})
        expected = {key: execution.get(key) for key in (
            "executionId", "nodeId", "epoch", "acceptedRevision", "assignmentDigest", "executionProtocolVersion", "budget")}
        expected.update(contextProtocolVersion=execution.get("contextProtocolVersion", 1),
                        contextVersion=assignment.get("contextVersion"))
        if (digest(assignment) != execution.get("assignmentDigest")
                or any(payload[key] != value for key, value in expected.items())
                or payload["authorityDeadlineAt"] != execution.get("budget", {}).get("runDeadlineAt")):
            raise ValueError("Intent differs from its original execution authority.")

    def _writable(self, project, workspace):
        if workspace == "architecture" or self.canvas.view(project, workspace).get("readOnly"):
            raise ValueError("Execution observer writes require a writable workspace.")

    def bind(self, payload, observer_id, config):
        intent(payload)
        project, workspace = scope(payload)
        with self.executions.transaction(project, workspace) as executions:
            self._writable(project, workspace)
            repo = ObserverRecords(executions.db, project, workspace)
            existing = repo.replay(payload, observer_id)
            execution = executions.read(payload["executionId"])
            self._binding(execution, payload)
            if existing:
                active = self.executions.response(executions, execution)["state"] == "running"
                return {**existing, "authorityActive": active}
            self.executions.active(executions, execution)
            if time.time() >= payload["authorityDeadlineAt"]:
                raise ValueError("Execution authority is no longer active.")
            if payload["provider"] != config["provider"] or int(payload["maxListCostCents"]) > int(config["maxListCostCents"]):
                raise ValueError("Intent exceeds the configured observer provider or list budget.")
            return {**repo.insert(payload, observer_id, now()), "authorityActive": True}

    def _reservation(self, project, workspace, intent_id, session_id, *, reserve=False):
        if session_id is None:
            return
        # Project locks precede this leaf registry lock. Reservation intentionally commits
        # before project evidence: a crash leaves an irrevocable same-intent reservation.
        with self.canvas.registry_lock:
            if reserve:
                with self.canvas.db:
                    self.canvas.db.execute("BEGIN IMMEDIATE")
                    sessions.reserve(self.canvas.db, project, workspace, intent_id, session_id)
            else:
                sessions.verify(self.canvas.db, project, workspace, intent_id, session_id)

    def observe(self, payload, observer_id, config):
        observation(payload)
        project, workspace = scope(payload)
        with self.executions.transaction(project, workspace) as executions:
            self._writable(project, workspace)
            repo = ObserverRecords(executions.db, project, workspace)
            bound = repo.read(payload["intentId"])
            if bound["observerId"] != observer_id or bound["provider"] != config["provider"]:
                raise ValueError("Observation does not belong to this independent observer.")
            existing = repo.replay(payload, observer_id, observed=True)
            if existing:
                self._reservation(project, workspace, bound["id"], existing["sessionId"])
                return existing
            previous = repo.head(bound["id"])
            if previous:
                self._reservation(project, workspace, bound["id"], previous["sessionId"])
            # Validate CAS/counters before taking a permanent global reservation.
            from backend.canvas.opora_execution_observer_validation import advance
            if payload["expectedObservationHead"] != (previous["id"] if previous else None):
                raise ValueError("Observation head changed.")
            advance(previous, payload)
            self._reservation(project, workspace, bound["id"], payload["sessionId"], reserve=True)
            # Accounting does not call active(), renew a lease, or authorize a result.
            return repo.insert(payload, observer_id, now(), observed=True)

    def summary(self, project, workspace, *, limit=100):
        scope({"project": project, "workspace": workspace})
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            view = self.canvas.view(project, workspace)
            repo = ObserverRecords(self.canvas.db_for(project), project, workspace)
            values = []
            for record in repo.intents(limit):
                head = repo.head(record["id"])
                if head:
                    self._reservation(project, workspace, record["id"], head["sessionId"])
                values.append({"intent": record, "observation": head,
                               "listBudgetExceeded": bool(head and int(head["cumulative"]["listCostCents"]) > int(record["maxListCostCents"]))})
            try:
                configured = any(value["project"] == project and value["workspace"] == workspace for value in observers().values())
            except ValueError:
                configured = False
            return {"items": values, "readOnly": bool(view.get("readOnly")),
                    "observerConfigured": configured, "providerAccessVerified": False,
                    "usageBasis": "observer-attested-provider-list-cost-not-invoice"}
