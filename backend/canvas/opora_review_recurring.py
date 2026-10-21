"""Recurring review misses become checks (docs/oporahub-review-identity.md, "Opakované nálezy").

A bug class is the second `:`-separated segment of a finding fingerprint (`path:class:symbol`),
or the whole fingerprint when it has no separator. A class posted on at least N distinct PRs of
the project (default 3, `OPORA_REVIEW_RECURRING_MIN_PRS`) and not yet promoted yields one
agent-state attention action `review.promote_to_check`. Recording the promotion (the check that
now catches the class) removes the action. Detection is read-only and deterministic."""
import os

from backend.canvas import opora_agent_state_rules as rules
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_review_insight_common import fields, project_id, reading, text, writing
from database.repositories.opora_review_insights import ReviewInsights

VERB = "review.promote_to_check"
PATH = "/api/oporahub/review-recurring/promote"
DEFAULT_MIN_PRS = 3


def min_prs():
    raw = os.environ.get("OPORA_REVIEW_RECURRING_MIN_PRS", "")
    value = int(raw) if raw.isdigit() else DEFAULT_MIN_PRS
    if not 2 <= value <= 50:
        raise ValueError("OPORA_REVIEW_RECURRING_MIN_PRS musí být 2–50.")
    return value


def bug_class(fingerprint):
    parts = fingerprint.split(":")
    return (parts[1] if len(parts) >= 2 and parts[1] else parts[0]).casefold()


def detect(db, project, threshold=None):
    """[{bugClass, prCount, prs, fingerprints, severities}] for unpromoted classes in ≥ threshold PRs."""
    threshold = threshold or min_prs()
    groups = {}
    for repo, number, fingerprint, severity in db.execute(
            "SELECT repository,number,fingerprint,severity FROM opora_review_findings WHERE project_id=?",
            (project,)).fetchall():
        group = groups.setdefault(bug_class(fingerprint), {"prs": set(), "fingerprints": set(), "severities": set()})
        group["prs"].add(f"{repo}#{number}")
        group["fingerprints"].add(fingerprint)
        group["severities"].add(severity)
    promoted = ReviewInsights(db, project).promoted()
    return [{"bugClass": name, "prCount": len(group["prs"]), "prs": sorted(group["prs"]),
             "fingerprints": len(group["fingerprints"]), "severities": sorted(group["severities"])}
            for name, group in sorted(groups.items())
            if len(group["prs"]) >= threshold and name not in promoted]


def actions(db, project):
    """Agent-state attention actions; the caller already holds the project locks."""
    threshold = min_prs()
    return [{"id": rules.stable_id("act_", VERB, item["bugClass"], item["prCount"]), "verb": VERB, "method": "POST",
             "path": PATH, "targetId": item["bugClass"], "status": "ready", "attention": True,
             "preconditions": {"bugClass": item["bugClass"], "prCount": item["prCount"], "minPrs": threshold}}
            for item in detect(db, project, threshold)]


def read_recurring(canvas, project):
    project = project_id(project)
    with reading(canvas, project) as (db, _):
        return {"minPrs": min_prs(), "items": detect(db, project)}


def promote(canvas, payload, actor):
    """Record the check that now covers a bug class; same check again is a no-op, another is 409."""
    fields(payload, ("project", "bugClass", "checkRef"))
    project = project_id(payload["project"])
    name, check = text(payload["bugClass"], "Třída chyby", 160).casefold(), text(payload["checkRef"], "Kontrola", 300)
    with writing(canvas, project) as (_, store):
        existing = store.promotion(name)
        if existing is not None and existing["checkRef"] != check:
            raise ValueError("Třída chyby už je povýšena na jinou kontrolu.")
        if existing is None:
            store.insert_promotion(name, check, actor, stamp())
        return store.promotion(name)
