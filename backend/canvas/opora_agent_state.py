"""One deterministic agent-state document composed read-only from existing OporaHub services.

Agents read this instead of polling every endpoint; the backend, not the model, derives
stage health, human decisions and the next ready/blocked actions with exact CAS values.
Contract and rules: docs/oporahub-agent-state.md. Nothing here writes or transitions state.
"""
import time
from datetime import UTC, datetime
from urllib.parse import urlencode

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas import opora_agent_state_rules as rules
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_process_sync import ProcessSync
from backend.canvas.opora_proposal_review_context import proposal as native_proposal
from backend.canvas.opora_proposal_risk import classify_risk
from database.repositories.opora_executions import Executions

SCHEMA_VERSION = 1
_KINDS = {"graph-additions": "graph-addition", "graph-changes": "graph-change",
          "content-proposal": "content"}
_PATHS = {"spec": "/api/oporahub/changesets/{}", "graph-addition": "/api/oporahub/graph-proposals/{}",
          "graph-change": "/api/oporahub/graph-proposals/{}", "content": "/api/oporahub/content-changes/{}"}


def _epoch(value):
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _action(verb, method, path, target, head, preconditions, blocked=None, budget=None):
    value = {"id": rules.stable_id("act_", verb, target, head), "verb": verb, "method": method,
             "path": path, "targetId": target, "preconditions": preconditions,
             "status": "blocked" if blocked else "ready"}
    if blocked:
        value["blockReason"] = blocked
    if budget is not None:
        value["budget"] = budget
    return value


class AgentState:
    def __init__(self, canvas, clock=time.time):
        self.canvas, self.clock = canvas, clock

    def proposals(self, db, project, workspace, accepted):
        families = [OporaChangesets(self.canvas).list(project, workspace)["items"],
                    OporaGraphProposals(self.canvas).list(project, workspace)["items"],
                    OporaContentChanges(self.canvas).list(project, workspace)["items"]]
        pending = []
        for items in families:
            superseded = {item.get("supersedes") for item in items} - {None}
            for item in items:
                if item["accepted"] or item["id"] in superseded:
                    continue
                kind = _KINDS.get(item.get("kind"), "spec")
                level = classify_risk(kind, native_proposal(db, project, workspace, kind, item["id"]))["level"]
                pending.append({"kind": kind, "id": item["id"], "subject": item.get("subject") or "",
                                "createdAt": _epoch(item.get("createdAt")), "risk": rules.RISK[level],
                                "stale": item["parentRevision"] != accepted})
        return sorted(pending, key=lambda item: (item["createdAt"], item["id"]))

    def executions(self, db, project, workspace):
        repo, latest = Executions(db, project, workspace), {}
        for record in repo.history():
            if record["nodeId"] in latest:
                continue
            deadline = min(record["expiresAt"], record.get("budget", {}).get("runDeadlineAt", record["expiresAt"]))
            latest[record["nodeId"]] = {"id": record["executionId"], "nodeId": record["nodeId"],
                                        "state": record["state"], "acceptedRevision": record["acceptedRevision"],
                                        "deadline": deadline, "results": len(repo.receipts(record["executionId"]))}
        return [latest[key] for key in sorted(latest)]

    def claims(self, project, workspace, cards):
        authority, result = OporaExecutions(self.canvas), []
        for card in cards:
            if card["status"] not in {"ready", "blocked"}:
                continue
            context = authority.context(project, workspace, card["nodeId"])
            budget = context.get("budget") or {}
            reason = budget.get("blockedReason")
            if card["status"] == "blocked" and not reason:
                continue
            result.append({"nodeId": card["nodeId"], "context": context, "budget": budget,
                           "status": "blocked" if reason else "ready",
                           "blockReason": None if not reason else
                           "budget_exhausted" if "exhausted" in reason else "budget_policy_required"})
        return result

    def read(self, project, workspace):
        scope({"project": project, "workspace": workspace})
        canvas, now = self.canvas, self.clock()
        with canvas.graph_lock_for(project), canvas.lock_for(project):
            db = canvas.db_for(project)
            context = OporaChangesets(canvas).context(project, workspace)
            accepted = context["acceptedHead"]
            process = ProcessSync(canvas).read(project, workspace)
            cards = {item["nodeId"]: item for item in process["items"]}
            pending = self.proposals(db, project, workspace, accepted)
            latest = self.executions(db, project, workspace)
            claims = self.claims(project, workspace, process["items"])
            linked = pulls.read(canvas, project, workspace)
        fresh = [item for item in pending if not item["stale"]]
        reported = [item for item in latest if item["results"]]
        to_review = [item for item in reported if item["acceptedRevision"] == accepted
                     and not cards.get(item["nodeId"], {}).get("doneConfirmed")]
        actions, decisions = self.actions(project, workspace, context, pending, claims, reported, to_review, linked, cards)
        heads = {"acceptedHead": accepted, "acceptedRevision": accepted, "graphDigest": context["graphDigest"],
                 "workingDiffers": context["workingDiffers"], "contextVersion": context["specificationsVersion"],
                 "budgetPolicyHead": {item["nodeId"]: item["budget"]["policyHead"]
                                      for item in claims if item["budget"].get("policyHead")}}
        stages = [rules.plan_stage(context), rules.proposal_stage(pending),
                  rules.acceptance_stage(context, fresh, now), rules.claim_stage(claims),
                  rules.work_stage(latest, now), rules.evidence_stage(reported, accepted),
                  rules.review_stage(to_review), *rules.pull_stages(reported, linked)]
        gaps = [*rules.GAPS, *([rules.PULL_GAP] if linked is None else [])]
        return {"schemaVersion": SCHEMA_VERSION,
                "generatedAt": datetime.fromtimestamp(now, UTC).isoformat(timespec="seconds"),
                "projectId": project, "workspaceId": workspace, "heads": heads, "stages": stages,
                "riskMix": {level: sum(item["risk"] == level for item in pending)
                            for level in ("low", "elevated", "critical")},
                "decisions": decisions, "actions": actions,
                "gaps": sorted(({"id": key, "stage": stage, "reason": reason} for key, stage, reason in gaps),
                               key=lambda item: item["id"]),
                "truncated": process["truncated"]}

    @staticmethod
    def actions(project, workspace, context, pending, claims, reported, to_review, linked, cards):
        accepted, graph, actions, decisions = context["acceptedHead"], context["graphDigest"], [], []
        query = urlencode({"project": project, "workspace": workspace})

        def decide(kind, target, title, action, order=0.0):
            decisions.append(((rules.DECISION_PRIORITY[kind], order, target),
                              {"id": "dec_" + action["id"][4:], "kind": kind, "targetId": target,
                               "title": title, "actionId": action["id"]}))

        if accepted is None and context["documents"]:
            action = _action("accept_baseline", "POST", "/api/oporahub/baselines", None, context["specificationsVersion"],
                             {"expectedAcceptedHead": None, "expectedGraphDigest": graph,
                              "expectedSpecificationsVersion": context["specificationsVersion"]}, "human_only")
            actions.append(action)
            decide("accept_baseline", None, "Přijmout výchozí zadání", action)
        for item in pending:
            path = _PATHS[item["kind"]].format(item["id"])
            if item["stale"]:
                actions.append(_action("rebase", "POST", path + "/rebase", item["id"], accepted,
                                       {"expectedAcceptedHead": accepted}))
                continue
            expected = {"expectedAcceptedHead": accepted}
            if item["kind"].startswith("graph"):
                expected["expectedGraphDigest"] = graph
            if item["kind"] == "graph-change":
                expected["reviewedChangesId"] = item["id"]
            if item["kind"] == "content":
                expected["reviewedProposalId"] = item["id"]
            action = _action("accept", "POST", path + "/accept", item["id"], accepted, expected, "human_only")
            actions.append(action)
            decide("accept_" + item["risk"], item["id"], item["subject"], action, item["createdAt"])
        for item in claims:
            ctx, budget = item["context"], item["budget"]
            expected = {"expectedAcceptedHead": ctx["acceptedHead"] or accepted,
                        "expectedContextVersion": ctx["contextVersion"]}
            if ctx.get("executionProtocolVersion") == 2:
                expected |= {"expectedBudgetPolicyHead": budget.get("policyHead"),
                             "previousExecutionId": budget.get("latestExecutionId")}
            spent = ({"remainingAttempts": budget["remainingAttempts"],
                      "remainingRepairRounds": budget["remainingRepairRounds"]} if budget.get("enrolled") else None)
            actions.append(_action("claim", "POST", "/api/oporahub/executions/claim", item["nodeId"],
                                   ctx["contextVersion"] or accepted, expected, item["blockReason"], spent))
        links = None if linked is None else {value["executionId"] for value in linked}
        for item in reported:
            if item in to_review:
                action = _action("review", "GET", f"/api/oporahub/executions/{item['id']}/results?{query}", item["id"],
                                 item["acceptedRevision"], {"acceptedRevision": item["acceptedRevision"]}, "human_only")
                actions.append(action)
                name = cards.get(item["nodeId"], {}).get("name") or item["nodeId"]
                decide("review_result", item["id"], f"Zkontrolovat nahlášený výsledek: {name}", action)
            if links is None or item["id"] not in links:
                actions.append(_action("link_pull_request", "POST", f"/api/oporahub/executions/{item['id']}/pull-request",
                                       item["id"], item["acceptedRevision"], {"acceptedRevision": item["acceptedRevision"]},
                                       "not_implemented" if links is None else None))
        actions.sort(key=lambda value: (rules.VERB_ORDER.index(value["verb"]), value["targetId"] or ""))
        decisions.sort(key=lambda value: value[0])
        return actions, [value for _, value in decisions[:rules.DECISION_LIMIT]]
