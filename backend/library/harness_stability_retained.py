"""Reassess retained native evidence without reviving its execution authority."""
from backend.canvas.graph import digest
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_verification_validation import identity
from backend.library import harness_verifier_plan as plans
from backend.library import harness_verifier_records as records
from backend.library.harness_stability import HarnessStability, policy
from database.repositories.opora_verifications import Verifications


class RetainedStability(HarnessStability):
    def assess(self, payload):
        project, workspace = validate(payload, {"verificationId"})
        identity(payload["verificationId"])
        configured, verifier = policy(project, workspace), plans.configuration(project, workspace)
        if (project, workspace) != (verifier["project"], verifier["workspace"]):
            raise ValueError("Verifier scope differs from stability policy.")
        with self.transaction(project, workspace) as repo:
            if workspace == "architecture" or self.canvas.view(project, workspace).get("readOnly"):
                raise ValueError("Stability requires a writable workspace.")
            store = Verifications(repo.db, project, workspace)
            request = store.read(payload["verificationId"])
            record = repo.read(request["executionId"])
            if digest(record.get("assignment")) != record.get("assignmentDigest"):
                raise ValueError("Retained accepted assignment is corrupt.")
            pinned = plans.prepare(record, request["origin"]["plan"])
            # Reconstruct the native request; a worker import or a foreign binding cannot
            # become a source merely by claiming a native origin or recomputing a digest.
            expected = records.request(record, pinned, verifier["image"])
            if (request["id"] != payload["verificationId"]
                    or any(request.get(k) != v for k, v in expected.items() if k not in {"id", "createdAt"})):
                raise ValueError("Retained verification is not bound to this accepted plan.")

            def source_current():
                if store.read(request["id"]) != request or repo.read(record["executionId"]) != record:
                    raise ValueError("Retained evidence changed during assessment.")

            result = self.snapshot(repo, record, pinned["resource"], configured, verifier, source_current)
            # All reports are validated by the common evaluator. The nominated source
            # must itself be among those proofs, not just coexist with a passing report.
            proof = next((r for r in result["comparison"]["reports"] if r["verificationId"] == request["id"]), None)
            if proof is None:
                result["eligible"] = False
                result["reasons"].append("retained-source-not-verified")
            result.update(schema="harness.retained-stability/1", executionAuthority=False,
                          source={"kind": "retained-native-verification", "verificationId": request["id"],
                                  "requestDigest": request["requestDigest"],
                                  "reportDigest": proof["reportDigest"] if proof else None})
            result.pop("evidenceDigest")
            return {**result, "evidenceDigest": digest(result)}
