"""One deterministic agent-state document composed read-only from existing OporaHub services.

Agents read this instead of polling every endpoint; the backend, not the model, derives
stage health, human decisions and the next ready/blocked actions with exact CAS values.
Contract and rules: docs/oporahub-agent-state.md. Nothing here writes or transitions state.
"""
import time
from datetime import UTC, datetime
from urllib.parse import urlencode

from backend.canvas import opora_agent_state_auto_rebase as rebasing_state
from backend.canvas import opora_agent_state_cards as card_stages
from backend.canvas import opora_agent_state_dag as dag_state
from backend.canvas import opora_agent_state_formal as formal
from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas import opora_agent_state_review_gates as review_gates
from backend.canvas import opora_agent_state_reviews as reviews
from backend.canvas import opora_agent_state_rules as rules
from backend.canvas import opora_agent_state_steps as plan_steps
from backend.canvas import opora_card_done as card_done
from backend.canvas import opora_review_recurring as recurring
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
            # A predecessor-blocked card keeps its claim action; dag_state.block_claims blocks it.
            if card["status"] == "blocked" and not reason and not card.get("blockedBy"):
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
            reviewing = reviews.read(canvas, project, workspace, now)
            attention = formal.attention(db, project, workspace)
            promotions = recurring.actions(db, project)  # Recurring misses → checks.
            rebasing = rebasing_state.read(canvas, project, workspace)
            dag = dag_state.facts(canvas, project, workspace, linked)  # Card DAG: blockedBy, topoIndex
            # Merged PRs too; None = review jobs disabled, GitHub branch protection is the gate.
            gates = card_done.gates_by_execution(db, project, workspace) if linked else {}
        dag_state.block_claims(claims, dag)
        fresh = [item for item in pending if not item["stale"]]
        reported = [item for item in latest if item["results"]]
        to_review = [item for item in reported if item["acceptedRevision"] == accepted
                     and not cards.get(item["nodeId"], {}).get("doneConfirmed")]
        actions, decisions = self.actions(project, workspace, context, pending, claims, reported, to_review, linked, cards,
                                          reviewing, gates)
        actions, decisions = formal.merge(actions, decisions, attention, project, workspace)
        # One priority list (rules.VERB_ORDER) over core, gate, formal, recurring and auto-rebase actions.
        actions = rules.ordered([*actions, *promotions, *rebasing_state.actions(project, workspace, rebasing)])
        actions = dag_state.retag(actions, dag)
        heads = {"acceptedHead": accepted, "acceptedRevision": accepted, "graphDigest": context["graphDigest"],
                 "workingDiffers": context["workingDiffers"], "contextVersion": context["specificationsVersion"],
                 "budgetPolicyHead": {item["nodeId"]: item["budget"]["policyHead"]
                                      for item in claims if item["budget"].get("policyHead")}}
        stages = [rules.plan_stage(context), rebasing_state.proposal_stage(pending, rebasing),
                  rules.acceptance_stage(context, fresh, now), rules.claim_stage(claims),
                  rules.work_stage(latest, now), rules.evidence_stage(reported, accepted),
                  rules.review_stage(to_review, reviewing), *rules.pull_stages(reported, linked)]
        gaps = [*rules.GAPS, *([rules.PULL_GAP] if linked is None else [])]
        gaps = [gap for gap in rebasing_state.gaps(gaps, rebasing) if reviewing is None or gap[0] != "ai_review"]
        return {"schemaVersion": SCHEMA_VERSION,
                "generatedAt": datetime.fromtimestamp(now, UTC).isoformat(timespec="seconds"),
                "projectId": project, "workspaceId": workspace, "heads": heads, "stages": stages,
                "riskMix": {level: sum(item["risk"] == level for item in pending)
                            for level in ("low", "elevated", "critical")},
                "decisions": decisions, "actions": actions,
                "gaps": sorted(({"id": key, "stage": stage, "reason": reason} for key, stage, reason in gaps),
                               key=lambda item: item["id"]),
                "cards": plan_steps.attach(dag_state.enrich(card_stages.project(cards, accepted, latest, claims, linked,
                                                                                reviewing, now), dag, actions, reviewing),
                                           cards, linked, gates),
                "truncated": process["truncated"]}

    @staticmethod
    def actions(project, workspace, context, pending, claims, reported, to_review, linked, cards, reviewing=None,
                gates=None):
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
        for item in linked or []:
            # Merge write-back never closes a card: done.confirmed stays a human action (oporahub-executions.md).
            if not item.get("awaitingHumanClose") or cards.get(item["cardId"], {}).get("doneConfirmed"):
                continue
            # Precondition = the single definition of done minus the human close (opora_card_done).
            done = card_done.card_done_state(card_done.facts(cards.get(item["cardId"], {}), item,
                                                             (gates or {}).get(item["executionId"]),
                                                             external=gates is None))
            ready = card_done.closable(done)
            action = _action("close_card", "POST", "/api/desktop-v3/state", item["cardId"], item.get("mergeSha"),
                             {"executionId": item["executionId"], "mergeSha": item.get("mergeSha"),
                              "missing": [name for name in done["missing"] if name != "human_close"],
                              "gate": done["gate"]},
                             "human_only" if ready else "done_state_incomplete")
            actions.append(action)
            name = cards.get(item["cardId"], {}).get("name") or item["cardId"]
            if ready:
                decide("close_card", item["cardId"], f"Uzavřít kartu po merge PR: {name}", action)
        for job in (reviewing or {}).get("claimable", []):
            actions.append(_action("review.claim", "POST", "/api/oporahub/review-jobs/claim", job["reviewJobId"],
                                   job["headSha"], {"role": job["role"], "headSha": job["headSha"]}))
        actions += review_gates.actions(reviewing)  # pr.update_branch, review.self_checks
        actions = rules.ordered(actions)
        decisions.sort(key=lambda value: value[0])
        return actions, [value for _, value in decisions[:rules.DECISION_LIMIT]]
