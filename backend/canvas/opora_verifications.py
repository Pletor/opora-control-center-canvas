"""Execution-fenced formal evidence imports never confer verifier authority."""
import time
import uuid

from backend.canvas import opora_verification_validation as validation
from backend.canvas.canvas_service import now
from backend.canvas.opora_execution_budget_runtime import check
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from database.repositories.opora_verifications import Verifications

TRUST = {"trust": "agent-reported", "independentlyVerified": False,
         "sourceBinding": "agent-reported", "currentEligibility": False}


class OporaVerifications(OporaExecutions):
    @staticmethod
    def store(repo):
        return Verifications(repo.db, *repo.scope)

    @staticmethod
    def availability(store, record):
        def descriptors(items):
            result = []
            for item in items:
                try:
                    store.blob(item["sha256"], item["bytes"])
                    available = True
                except ValueError:
                    available = False
                result.append({**item, "available": available})
            return result
        value = {**record, "verification": {**record["verification"],
                 "artifacts": descriptors(record["verification"]["artifacts"])}}
        if record["report"]:
            value["report"] = {**record["report"], "artifacts": descriptors(record["report"]["artifacts"])}
        return value

    def history(self, project, workspace, node=None, *, domain="formal"):
        validate({"project": project, "workspace": workspace, **({"nodeId": node} if node is not None else {})},
                 {"nodeId"} if node is not None else set())
        with self.transaction(project, workspace) as repo:
            store = self.store(repo)
            return {"requests": [self.availability(store, item) for item in store.history(node, domain)]}

    def read(self, identifier, project, workspace):
        validation.identity(identifier)
        validate({"project": project, "workspace": workspace}, set())
        with self.transaction(project, workspace) as repo:
            store = self.store(repo)
            return self.availability(store, store.read(identifier))

    def artifact(self, identifier, fingerprint, project, workspace):
        validation.identity(identifier)
        validation.sha(fingerprint)
        validate({"project": project, "workspace": workspace}, set())
        with self.transaction(project, workspace) as repo:
            store = self.store(repo)
            record = store.read(identifier)
            manifests = record["verification"]["artifacts"] + ((record["report"] or {}).get("artifacts", []))
            descriptor = next((item for item in manifests if item["sha256"] == fingerprint), None)
            if descriptor is None:
                raise ValueError("Artifact is not in this verification manifest.")
            return store.blob(fingerprint, descriptor["bytes"])

    def create(self, payload):
        project, workspace = validate(payload, {"executionId", "token", "epoch", "requestId", "verification"})
        validation.identity(payload["executionId"])
        metadata, blobs = validation.verification(payload["verification"])
        with self.transaction(project, workspace) as repo:
            execution = repo.read(payload["executionId"])
            self.authenticate(execution, payload["token"], payload["epoch"])
            fingerprint = validation.digest({key: execution[key] for key in
                ("project", "workspace", "nodeId", "executionId", "epoch", "acceptedRevision", "assignmentDigest")} | {"verification": metadata})
            store = self.store(repo)
            replay = store.replay(execution["executionId"], payload["requestId"])
            if replay:
                if replay[0] != fingerprint:
                    raise ValueError("Verification request identity was already used for different content.")
                return replay[1]
            self.active(repo, execution)
            record = {"id": uuid.uuid4().hex, "project": project, "workspace": workspace,
                      "nodeId": execution["nodeId"], "executionId": execution["executionId"], "epoch": execution["epoch"],
                      "acceptedRevision": execution["acceptedRevision"], "assignmentDigest": execution["assignmentDigest"],
                      "requestId": payload["requestId"], "requestDigest": fingerprint,
                      "manifestDigest": validation.digest(metadata["artifacts"]), "verification": metadata,
                      "createdAt": now(), **TRUST}
            store.store_blobs(blobs)
            self.lease_valid(repo, execution)
            check(repo.db, repo.scope, execution, time.time())
            store.insert(record)
            return {**record, "report": None}

    def submit_report(self, identifier, payload):
        validation.identity(identifier)
        project, workspace = validate(payload, {"token", "epoch", "requestId", "report"})
        with self.transaction(project, workspace) as repo:
            store = self.store(repo)
            request = store.read(identifier)
            if request.get("trust") != "agent-reported":
                raise ValueError("Server-owned verification reports cannot be imported by a worker.")
            execution = repo.read(request["executionId"])
            self.authenticate(execution, payload["token"], payload["epoch"])
            metadata, blobs = validation.report(payload["report"], request["verification"]["claims"])
            fingerprint = validation.digest({"verificationId": identifier, "requestDigest": request["requestDigest"], "report": metadata})
            prior = request["report"]
            if prior:
                if prior["requestId"] != payload["requestId"] or prior["reportDigest"] != fingerprint:
                    raise ValueError("Verification already has a different report.")
                return prior
            self.active(repo, execution)
            combined = request["verification"]["artifacts"] + metadata["artifacts"]
            if sum(item["bytes"] for item in combined) > validation.RUN_LIMIT:
                raise ValueError("Verification inputs and outputs exceed 8 MiB.")
            record = {**metadata, "requestId": payload["requestId"], "reportDigest": fingerprint,
                      "manifestDigest": validation.digest(metadata["artifacts"]), "createdAt": now(), **TRUST}
            store.store_blobs(blobs)
            self.lease_valid(repo, execution)
            check(repo.db, repo.scope, execution, time.time())
            store.insert_report(identifier, record)
            return record
