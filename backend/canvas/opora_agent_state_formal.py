"""Counterexample -> attention: failing `formal/tlc` evidence becomes a decision and an action.

Read-only, derived on every agent-state read from the verification store: for each
execution the newest CI-observed `formal/tlc` record counts; a later pass on a newer
head clears it. Every non-passing outcome yields the ready agent action
`verification.investigate` (read the stored evidence) and a human decision that points
to it. Contract: docs/oporahub-agent-state.md, docs/oporahub-verification.md.
"""
import json
from urllib.parse import urlencode

from backend.canvas import opora_agent_state_rules as rules

VERB = "verification.investigate"
ATTENTION = {"counterexample": "verification_counterexample", "failed": "verification_failed",
             "inconclusive": "verification_failed"}
TITLES = {"verification_counterexample": "Formální model našel protipříklad: {}",
          "verification_failed": "Formální kontrola selhala: {}"}


def attention(db, project, workspace, limit=200):
    rows = db.execute("SELECT q.record, r.record FROM opora_verification_requests q "
                      "LEFT JOIN opora_verification_reports r ON r.verification_id=q.id "
                      "WHERE q.project_id=? AND q.workspace_id=? AND q.request_id LIKE 'gh-check-%' "
                      "ORDER BY q.rowid DESC LIMIT ?", (project, workspace, limit)).fetchall()
    latest = {}
    for request, report in rows:
        record = json.loads(request)
        if record["executionId"] in latest or report is None:
            continue
        latest[record["executionId"]] = {"verificationId": record["id"], "executionId": record["executionId"],
                                         "nodeId": record["nodeId"], "outcome": json.loads(report)["outcome"],
                                         "headSha": record["verification"]["source"]["commitSha"],
                                         "kinds": record.get("origin", {}).get("failureKinds", [])}
    return [item for _, item in sorted(latest.items()) if item["outcome"] in ATTENTION]


def merge(actions, decisions, items, project, workspace):
    """Formal attention leads the decisions (safety signal); actions keep their stable order."""
    query = urlencode({"project": project, "workspace": workspace})
    extra_actions, extra_decisions = [], []
    for item in items:
        kind = ATTENTION[item["outcome"]]
        action = {"id": rules.stable_id("act_", VERB, item["verificationId"], item["headSha"]), "verb": VERB,
                  "method": "GET", "path": f"/api/oporahub/verifications/{item['verificationId']}?{query}",
                  "targetId": item["executionId"],
                  "preconditions": {"headSha": item["headSha"], "verificationId": item["verificationId"],
                                    "outcome": item["outcome"], "failureKinds": item["kinds"]},
                  "status": "ready"}
        extra_actions.append(action)
        extra_decisions.append({"id": "dec_" + action["id"][4:], "kind": kind, "targetId": item["executionId"],
                                "title": TITLES[kind].format(item["nodeId"]), "actionId": action["id"]})
    return actions + extra_actions, (extra_decisions + decisions)[:rules.DECISION_LIMIT]
