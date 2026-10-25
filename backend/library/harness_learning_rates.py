"""Explicitly scoped binomial rates of selected-kit outcomes; not causal attribution."""
import math

from backend.library.harness_guardrails import read as guardrails
from database.repositories.harness_learning import summaries


def rate(passed, failed, unknown):
    n, z = passed + failed, 1.959963984540054
    interval = None
    if n:
        p = passed / n
        denominator = 1 + z * z / n
        centre = (p + z * z / (2 * n)) / denominator
        margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
        interval = [100 * max(0, centre - margin), 100 * min(1, centre + margin)]
    return {"pass": passed, "fail": failed, "unknown": unknown, "executions": n + unknown,
            "percent": 100 * passed / n if n else None, "interval95": interval,
            "coverage": n / (n + unknown) if n + unknown else None}


def read(db, project, workspace, *, node=None, resource=None, limit=100):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Harness measurement limit must be 1-100.")
    rows = summaries(db, project, workspace, node=node, resource=resource, limit=limit)
    cohorts = [{"resource": row[0], "digest": row[1], "versionDigest": row[2], "category": row[3],
                "problem": row[4], "signal": "acceptance", "tier": row[5],
                "rate": rate(row[6], row[7], row[8]), "tasks": row[9], "lastSourceEvent": row[10],
                "enrolledSince": row[11], "runner": None,
                "invocationObserved": False, "meanDurationMs": None, "tokens": None, "cost": None}
               for row in rows[:limit]]
    for cohort in cohorts:
        cohort["guardrails"] = guardrails(db, project, workspace, cohort, node)
    return {"schema": "harness.learning/1", "authority": "native-outbox-projection",
            "scope": {"project": project, "workspace": workspace, "nodeId": node},
            "coverage": "since-kit-enrollment; no historical backfill",
            "association": "selected-kit; invocation and causal contribution unobserved",
            "verifiedMeaning": "human closure of the uniquely linked merged run at the pinned specification",
            "promotionAllowed": False, "limited": len(rows) > limit, "cohorts": cohorts}
