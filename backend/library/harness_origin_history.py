"""Bounded native outcomes grouped by pinned, caller-declared selection origins.

Origins are not authoritative ancestry. Multiple origins overlap: never sum their
cohorts as independent executions. Current graph/profile changes are not consulted.
"""
import json

from backend.canvas.graph import digest
from backend.library.harness_kit import kit_of_assignment
from backend.library.harness_learning_rates import rate
from backend.library.harness_selection import SCOPES, version_digest


def _pinned(row, project, workspace):
    execution, node, assignment_digest, revision, kit_digest, raw = row
    record = json.loads(raw)
    if (record.get("project"), record.get("workspace"), record.get("executionId"),
        record.get("nodeId"), record.get("assignmentDigest"), record.get("acceptedRevision")) != (
            project, workspace, execution, node, assignment_digest, revision):
        raise ValueError("Enrollment identity mismatch.")
    if record.get("contextProtocolVersion") != 2 or digest(record["assignment"]) != assignment_digest:
        raise ValueError("Assignment integrity mismatch.")
    kit = kit_of_assignment(record["assignment"], node)
    if kit is None or digest(kit) != kit_digest:
        raise ValueError("Kit enrollment mismatch.")
    return kit


def read(db, project, workspace, *, node=None, resource=None, origin_scope=None,
         origin_node=None, limit=100):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Origin history window must be 1-100 executions.")
    if origin_scope is not None and origin_scope not in SCOPES | {"unknown"}:
        raise ValueError("Unknown Harness origin scope.")
    if origin_node is not None and origin_scope in {None, "global", "repository", "unknown"}:
        raise ValueError("Origin node needs a node-bearing origin scope.")
    condition = "r.project_id=? AND r.workspace_id=?"
    args = [project, workspace]
    if node is not None:
        condition += " AND r.node_id=?"
        args.append(node)
    rows = db.execute(
        "SELECT r.execution_id,r.node_id,r.assignment_digest,r.accepted_revision,r.kit_digest,e.record"
        " FROM harness_learning_runs r LEFT JOIN opora_executions e"
        " ON e.project_id=r.project_id AND e.workspace_id=r.workspace_id AND e.id=r.execution_id"
        " WHERE " + condition + " ORDER BY r.rowid DESC LIMIT ?", (*args, limit + 1)).fetchall()
    cohorts, excluded, overflow = {}, 0, 0
    for row in rows[:limit]:
        try:
            kit = _pinned(row, project, workspace)
        except (ValueError, TypeError, KeyError, AttributeError):
            excluded += 1
            continue
        outcomes = dict(db.execute(
            "SELECT tier,outcome FROM harness_learning_outcomes"
            " WHERE project_id=? AND workspace_id=? AND execution_id=?", (project, workspace, row[0])))
        selection = kit.get("selection", {}).get("entries", [])
        for index, item in enumerate(kit["resources"]):
            if resource is not None and item["resource"] != resource:
                continue
            origins = {(entry["scope"], entry["node"])
                       for entry in selection[index]["assignments"]} if selection else set()
            origins = origins or {("unknown", None)}
            for level, source in sorted(origins, key=lambda value: (value[0], value[1] or "")):
                if origin_scope is not None and level != origin_scope:
                    continue
                if origin_node is not None and source != origin_node:
                    continue
                for problem in kit["problems"]:
                    for tier in ("reported", "verified"):
                        key = (item["resource"], version_digest(item), problem, tier, level, source)
                        if key not in cohorts:
                            if len(cohorts) >= 100:
                                overflow += 1
                                continue
                            cohorts[key] = {"resource": item["resource"], "digest": item["digest"],
                                "versionDigest": key[1], "category": item["category"],
                                "problem": problem, "tier": tier,
                                "origin": {"scope": level, "node": source},
                                "counts": {"pass": 0, "fail": 0, "unknown": 0}, "nodes": set()}
                        cohort = cohorts[key]
                        outcome = outcomes.get(tier, "unknown")
                        cohort["counts"][outcome if outcome in {"pass", "fail"} else "unknown"] += 1
                        cohort["nodes"].add(row[1])
    result = []
    for cohort in cohorts.values():
        counts = cohort.pop("counts")
        cohort["tasks"] = len(cohort.pop("nodes"))
        cohort["rate"] = rate(counts["pass"], counts["fail"], counts["unknown"])
        result.append(cohort)
    return {"schema": "harness.origin-history/1", "authority": "native-outbox-projection",
            "scope": {"project": project, "workspace": workspace, "nodeId": node},
            "originEvidence": "caller-declared-selection-origin; not verified ancestry",
            "association": "selected-kit; origins overlap; do not sum across origins",
            "verifiedMeaning": "human closure of linked merged run, not verification of origin",
            "window": {"kind": "newest-enrolled-executions", "limit": limit,
                       "examined": min(len(rows), limit), "excluded": excluded},
            "limited": len(rows) > limit or overflow > 0,
            "omittedCohortContributions": overflow, "cohorts": result,
            "promotionAllowed": False, "causalContribution": False, "invocationObserved": False}
