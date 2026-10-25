"""Native project eligibility for a future stable transition, never an approval or mutation."""
import importlib
import os
import re

from backend.canvas.graph import digest
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.library import harness_stability_cohort as cohorts
from backend.library import harness_stability_fixtures as fixtures
from backend.library import harness_verifier_plan as plans
from backend.library.harness_scope_config import select


def policy(project, workspace):
    raw = os.environ.get("OPORA_HARNESS_STABILITY", "")
    if not raw:
        raise ValueError("Harness stability policy is disabled.")
    return select(raw, _policy, project, workspace)


def _policy(value):
    if set(value) != {"project", "workspace", "approvedPlanDigests"}:
        raise ValueError("Invalid Harness stability policy.")
    scope(value)
    allowed = value["approvedPlanDigests"]
    if (not isinstance(allowed, list) or not 1 <= len(allowed) <= 32
            or not all(isinstance(v, str) and re.fullmatch(r"[a-f0-9]{64}", v) for v in allowed)
            or len(set(allowed)) != len(allowed)):
        raise ValueError("Stability requires distinct approved fault-plan digests in this scope.")
    return {**value, "approvedPlanDigests": sorted(allowed),
            "minimumVerifiedOutcomes": 20, "minimumVerifiedCards": 5, "minimumCoveragePercent": 95}


def candidate_resource(record, pinned):
    documents = record["assignment"]["documents"]
    target = [d for d in documents if d.get("nodeId") == record["nodeId"]]
    if len(target) != 1:
        raise ValueError("An exact accepted target is required.")
    resources = target[0]["fields"]["harness"]["resources"]
    candidates = [r for r in resources if r["resource"] == pinned["candidate"]["id"]]
    if (len(candidates) != 1 or candidates[0]["digest"] != pinned["candidate"]["digest"]
            or candidates[0]["category"] != "scripts" or candidates[0]["requires"] != ["command:node"]):
        raise ValueError("Only the accepted Node comparison candidate is supported.")
    return candidates[0]


def regression_evidence(db, project, workspace, resource, problem, version):
    try:
        reader = importlib.import_module("backend.library.harness_guardrails").read
    except ModuleNotFoundError as exc:
        if exc.name != "backend.library.harness_guardrails":
            raise
        return None
    return reader(db, project, workspace, {"resource": resource, "problem": problem, "versionDigest": version})


class HarnessStability(OporaExecutions):
    def assess(self, payload):
        project, workspace = validate(payload, {"executionId", "token", "epoch", "plan"})
        configured = policy(project, workspace)
        verifier = plans.configuration(project, workspace)
        if (project, workspace) != (verifier["project"], verifier["workspace"]):
            raise ValueError("Verifier scope differs from stability policy.")
        with self.transaction(project, workspace) as repo:
            record = repo.read(payload["executionId"])
            self.authenticate(record, payload["token"], payload["epoch"])
            self.active(repo, record)
            if workspace == "architecture" or self.canvas.view(project, workspace).get("readOnly"):
                raise ValueError("Stability requires a writable workspace.")
            return self.snapshot(repo, record, payload["plan"], configured, verifier,
                                 lambda: self.active(repo, record))

    def snapshot(self, repo, record, reference, configured, verifier, assert_current):
        """One evidence evaluator; caller owns the appropriate source-authority boundary."""
        project, workspace = repo.scope
        pinned = plans.prepare(record, reference)
        resource = candidate_resource(record, pinned)
        problem = pinned["plan"]["problem"]
        reasons = []
        if pinned["resource"]["digest"] not in configured["approvedPlanDigests"]:
            reasons.append("fault-plan-not-approved")
        cohort = cohorts.read(repo.db, project, workspace, resource, problem)
        guardrails = None
        if cohort is None:
            reasons.append("native-cohort-unavailable")
        else:
            if cohort["verifiedPasses"] < configured["minimumVerifiedOutcomes"]:
                reasons.append("insufficient-verified-outcomes")
            if cohort["verifiedCards"] < configured["minimumVerifiedCards"]:
                reasons.append("insufficient-verified-cards")
            if cohort["verifiedPasses"] * 100 < cohort["executions"] * configured["minimumCoveragePercent"]:
                reasons.append("insufficient-evidence-coverage")
            guardrails = regression_evidence(repo.db, project, workspace, resource["resource"], problem, cohort["versionDigest"])
            if guardrails is None:
                reasons.append("native-regressions-unavailable")
            elif guardrails["affectedExecutions"]:
                reasons.append("linked-regression")
        comparison = fixtures.read(repo.db, project, workspace, pinned, verifier["image"])
        if not comparison["complete"]:
            reasons.append(comparison["reason"])
        # The lock/transaction owns the evidence snapshot; a later transition must reread it.
        assert_current()
        if configured != policy(project, workspace) or verifier != plans.configuration(project, workspace):
            raise ValueError("Stability policy changed during assessment.")
        result = {"schema": "harness.stability-eligibility/1", "authority": "native-policy-assessment",
                  "scope": {"project": project, "workspace": workspace, "problem": problem},
                  "execution": {key: record[key] for key in ("executionId", "nodeId", "epoch", "acceptedRevision", "assignmentDigest")},
                  "candidate": pinned["candidate"], "baseline": pinned["baseline"], "plan": pinned["resource"],
                  "policy": configured, "policyDigest": digest(configured), "cohort": cohort,
                  "guardrails": guardrails, "comparison": comparison, "eligible": not reasons,
                  "reasons": reasons, "promotionAllowed": False, "reservation": False,
                  "evidenceBasis": {"taskOutcomes": "selected-kit-association", "taskInvocationVerified": False,
                                    "causalBenefitEstablished": False, "directObservation": "approved-fixture-cases-only"},
                  "meaning": "Project recommendation eligibility only; no stable state, global or production claim."}
        return {**result, "evidenceDigest": digest(result)}
