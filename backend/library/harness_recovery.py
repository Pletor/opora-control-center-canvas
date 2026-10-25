"""Recover a prior same-card kit version as a proposal, never a live assignment edit."""
import copy

from backend.canvas.graph import digest
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.opora_verification_validation import identity
from backend.library.harness_guardrails import read as guardrails
from backend.library.harness_kit import IDENTIFIER, kit_of_assignment, validate_kit


def _kit(record):
    if (record.get("contextProtocolVersion") != 2
            or digest(record["assignment"]) != record["assignmentDigest"]):
        raise ValueError("Recovery requires an intact immutable assignment.")
    kit = kit_of_assignment(record["assignment"], record["nodeId"])
    if kit is None:
        raise ValueError("Execution has no pinned Harness kit.")
    return kit


def _fixture_state(db, project, workspace, resource, content_digest):
    try:
        from backend.library.harness_verifier_quarantine import FAILURES
    except ModuleNotFoundError as error:
        if error.name != "backend.library.harness_verifier_quarantine":
            raise
        return "unavailable"
    rows = db.execute(FAILURES + "SELECT bound,candidate,digest FROM classified", (project, workspace))
    for bound, candidate, observed in rows:
        if not bound or (candidate == resource and observed == content_digest):
            raise ValueError("Historical version has unresolved native fixture quarantine.")
    return "no-recorded-failure"


class HarnessRecovery(OporaExecutions):
    def preview(self, payload):
        project, workspace = validate(payload, {"executionId", "token", "epoch", "sourceExecutionId", "resource"})
        for key in ("executionId", "sourceExecutionId"):
            identity(payload[key])
        resource = payload["resource"]
        if not isinstance(resource, str) or not IDENTIFIER.fullmatch(resource):
            raise ValueError("Invalid resource identity.")
        with self.transaction(project, workspace) as repo:
            current = repo.read(payload["executionId"])
            self.authenticate(current, payload["token"], payload["epoch"])
            self.active(repo, current)
            previous = repo.read(payload["sourceExecutionId"])
            if (previous["nodeId"] != current["nodeId"] or previous["epoch"] >= current["epoch"]):
                raise ValueError("Recovery source must be an earlier execution of this card.")
            present, old = _kit(current), _kit(previous)
            enrollment = repo.db.execute("SELECT node_id,assignment_digest,accepted_revision,kit_digest "
                "FROM harness_learning_runs WHERE project_id=? AND workspace_id=? AND execution_id=?",
                (project, workspace, previous["executionId"])).fetchone()
            expected = (previous["nodeId"], previous["assignmentDigest"], previous["acceptedRevision"], digest(old))
            if enrollment is None or tuple(enrollment) != expected:
                raise ValueError("Historical assignment does not match its native enrollment.")
            if set(present["problems"]) != set(old["problems"]):
                raise ValueError("Recovery source has a different problem scope.")
            selected = next((entry for entry in present["resources"] if entry["resource"] == resource), None)
            source = next((entry for entry in old["resources"] if entry["resource"] == resource), None)
            if (selected is None or source is None or selected["category"] != source["category"]
                    or set(selected["requires"]) != set(source["requires"])):
                raise ValueError("Historical resource is absent or has incompatible requirements.")
            if selected["digest"] == source["digest"]:
                raise ValueError("Current assignment already contains that content version.")
            version = digest({key: source[key] for key in ("resource", "category", "digest", "requires")})
            for problem in present["problems"]:
                cohort = {"resource": resource, "versionDigest": version, "problem": problem}
                if guardrails(repo.db, project, workspace, cohort)["affectedExecutions"]:
                    raise ValueError("Historical version has native incident or revert associations.")
            fixture_state = _fixture_state(repo.db, project, workspace, resource, source["digest"])
            outcome = repo.db.execute("SELECT outcome,source_event FROM harness_learning_outcomes "
                "WHERE project_id=? AND workspace_id=? AND execution_id=? AND tier='verified'",
                (project, workspace, previous["executionId"])).fetchone()
            if outcome and outcome[0] == "fail":
                raise ValueError("Historical execution has a current verified failure.")
            proposed = copy.deepcopy(present)
            replacement = {**source, "slot": selected["slot"]}
            proposed["resources"] = [replacement if entry["resource"] == resource else entry
                                     for entry in proposed["resources"]]
            # A replacement has no claim to the current selection rationale. Only the
            # NEW proposal loses provenance; the accepted historical/current kits remain intact.
            if proposed["schema"] == "harness.kit/2":
                proposed = {key: proposed[key] for key in ("schema", "problems", "resources")}
                proposed["schema"] = "harness.kit/1"
            validate_kit(proposed)
            self.active(repo, current)
            return {"schema": "harness.recovery-proposal/1", "scope": {"project": project, "workspace": workspace,
                    "nodeId": current["nodeId"]}, "executionId": current["executionId"], "epoch": current["epoch"],
                    "assignmentDigest": current["assignmentDigest"], "acceptedRevision": current["acceptedRevision"],
                    "source": {"executionId": previous["executionId"], "assignmentDigest": previous["assignmentDigest"],
                               "acceptedRevision": previous["acceptedRevision"], "resource": resource,
                               "digest": source["digest"], "versionDigest": version},
                    "evidence": {"verifiedOutcome": outcome[0] if outcome else "unknown",
                                 "sourceEvent": outcome[1] if outcome else None, "fixtureHistory": fixture_state},
                    "kit": proposed, "requiresAcceptance": True, "promotionAllowed": False,
                    "meaning": "Historical content is a recovery candidate, not certified stable. "
                               "Review and accept a new specification; the running assignment is unchanged."}
