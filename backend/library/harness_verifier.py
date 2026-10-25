"""Admit once, rerun outside transactions, retain independent fixture observations."""
import threading
import time

from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.opora_verification_validation import identity
from backend.library import harness_exploration as exploration
from backend.library import harness_verifier_budget as budget
from backend.library import harness_verifier_plan as plans
from backend.library import harness_verifier_records as records
from backend.library.harness_verifier_runner import cleanup_run, run_paired_fixture
from database.repositories.opora_verifications import Verifications

_running = threading.Lock()


def _remember(db, request):
    """Optional native memory projection joins the report transaction; never task-success credit."""
    try:
        from database.repositories.harness_fixture_memory import enqueue
    except ModuleNotFoundError as exc:
        if exc.name != "database.repositories.harness_fixture_memory":
            raise
        return {"available": False}
    enqueue(db, request["project"], request["workspace"], request["id"])
    return {"available": True}


class HarnessVerifier(OporaExecutions):
    def _current(self, payload, original):
        try:
            config = plans.configuration(payload["project"], payload["workspace"])
            if any(config[key] != original[key] for key in ("project", "workspace")) or config["image"] != original["origin"]["image"]:
                return False
            with self.transaction(payload["project"], payload["workspace"]) as repo:
                if not exploration.current(repo.db, original["project"], original["workspace"], original.get("exploration", {}).get("policyDigest")):
                    return False
                execution = repo.read(payload["executionId"])
                self.authenticate(execution, payload["token"], payload["epoch"])
                self.active(repo, execution)
                return all(execution[key] == original[key] for key in records.BINDING)
        except (ValueError, KeyError):
            return False

    def _admit(self, payload, config):
        project, workspace = payload["project"], payload["workspace"]
        with self.transaction(project, workspace) as repo:
            execution = repo.read(payload["executionId"])
            self.authenticate(execution, payload["token"], payload["epoch"])
            if workspace == "architecture" or self.canvas.view(project, workspace).get("readOnly"):
                raise ValueError("Verifier requires a writable workspace.")
            pinned = plans.prepare(execution, payload["plan"])
            proposed = records.request(execution, pinned, config["image"])
            store = Verifications(repo.db, project, workspace)
            replay = store.replay(execution["executionId"], proposed["requestId"])
            if replay:
                if replay[0] != proposed["requestDigest"]:
                    raise ValueError("This execution already admitted a different verifier plan.")
                if replay[1]["report"] is not None:
                    replay[1]["memoryDelivery"] = _remember(repo.db, replay[1])
                return replay[1], pinned, False
            self.active(repo, execution)
            pending = repo.db.execute(
                "SELECT 1 FROM opora_verification_requests r WHERE project_id=? AND workspace_id=? "
                "AND json_extract(r.record,'$.origin.kind')=? AND NOT EXISTS "
                "(SELECT 1 FROM opora_verification_reports p WHERE p.verification_id=r.id) LIMIT 1",
                (project, workspace, records.KIND)).fetchone()
            if pending:
                raise ValueError("A verifier admission is pending; reconcile that run first.")
            # Admission rows are the durable spent-attempt ledger, including interrupted runs.
            if budget.spent(repo.db, project, workspace) >= config["maxExperiments"]:
                raise ValueError("Harness experiment ceiling exhausted; a server policy change is required.")
            proposed["exploration"] = exploration.admit(repo.db, project, workspace, execution["nodeId"])
            proposed["deadlineAt"] = time.time() + 90
            store.insert(proposed)
            return {**proposed, "report": None}, pinned, True

    def verify(self, payload):
        project, workspace = validate(payload, {"executionId", "token", "epoch", "plan"})
        identity(payload["executionId"])
        config = plans.configuration(payload["project"], payload["workspace"])
        if (project, workspace) != (config["project"], config["workspace"]):
            raise ValueError("Verifier is not configured for this scope.")
        if not _running.acquire(blocking=False):
            raise ValueError("Harness verifier is busy.")
        try:
            request, pinned, admitted = self._admit(payload, config)
            if request["report"] is not None:
                return request
            if not admitted:
                if time.time() < request["deadlineAt"]:
                    return request  # Never restart a potentially live run on request replay.
                observed = records.interrupted(request["plannedTrials"], cleanup_run(request["id"], request["plannedTrials"]))
            else:
                try:
                    observed = run_paired_fixture(pinned, config["image"], lambda: self._current(payload, request), request["id"])
                except Exception:  # noqa: BLE001 -- preserve admission after unexpected executor failure.
                    # Even unexpected runner failure consumes admission and retains unknown coverage.
                    observed = records.interrupted(request["plannedTrials"], cleanup_run(request["id"], request["plannedTrials"]))
            current = self._current(payload, request)
            if not observed["cleanupComplete"]:
                # A terminal report would release the durable admission while a container may
                # still be running. Retain pending/unknown; replay after deadline retries cleanup.
                return {**request, "recoveryRequired": True}
            with self.transaction(project, workspace) as repo:
                store = Verifications(repo.db, project, workspace)
                saved = store.read(request["id"])
                if saved["report"] is not None:
                    return {**saved, "memoryDelivery": _remember(repo.db, saved)}
                # Recheck authority in the write transaction; historical evidence may still be retained.
                try:
                    execution = repo.read(payload["executionId"])
                    self.active(repo, execution)
                    current = current and all(execution[key] == request[key] for key in records.BINDING)
                except ValueError:
                    current = False
                result = records.report(request, observed, current)
                store.insert_report(request["id"], result)
                return {**saved, "report": result, "memoryDelivery": _remember(repo.db, saved)}
        finally:
            _running.release()
