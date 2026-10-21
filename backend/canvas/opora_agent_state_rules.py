"""Deterministic health rules of the agent-state loop; constants are the documented contract.

Every stage is computed from already-collected facts and an explicit `now`, so the same
stored state and clock always produce the same document (docs/oporahub-agent-state.md).
"""
import hashlib
import json

STAGES = ("plan", "proposal", "acceptance", "claim", "work", "evidence", "review",
          "pull_request", "merge", "plan_writeback")
ACCEPTANCE_WAIT_SECONDS = 24 * 3600  # Fresh proposal pending longer than this → waiting.
DECISION_LIMIT = 3
RISK = {"standard": "low", "elevated": "elevated", "critical": "critical"}
DECISION_PRIORITY = {"accept_baseline": 0, "accept_critical": 1, "accept_elevated": 2,
                     "accept_low": 3, "review_result": 4}
VERB_ORDER = ("accept_baseline", "accept", "rebase", "claim", "review", "link_pull_request")
GAPS = (("ai_review", "review", "Nezávislé AI review výsledků není napojeno; kontrolu dělá člověk."),
        ("lean_verification", "evidence", "Lean ověření úloh se zatím nespouští automaticky."),
        ("auto_rebase", "proposal", "Zastaralé návrhy se nepřevádějí automaticky; rebase je výslovný."))
PULL_GAP = ("pull_request_link", "pull_request", "Modul vazby execution → PR není nainstalován.")


def stable_id(prefix, *parts):
    raw = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def stage(identifier, count, health, reason):
    return {"id": identifier, "count": count, "health": health, "reason": reason}


def plan_stage(context):
    count = len(context["documents"])
    if count == 0:
        return stage("plan", 0, "waiting", "empty_plan")
    if context["acceptedHead"] is None:
        return stage("plan", count, "blocking", "no_accepted_baseline")
    if context["workingDiffers"]:
        return stage("plan", count, "waiting", "working_differs_from_accepted")
    return stage("plan", count, "ok", "accepted_plan_current")


def proposal_stage(pending):
    if any(item["stale"] for item in pending):
        return stage("proposal", len(pending), "waiting", "stale_proposals")
    return stage("proposal", len(pending), "ok", "proposals_current" if pending else "no_pending_proposals")


def acceptance_stage(context, fresh, now):
    if context["acceptedHead"] is None and context["documents"]:
        return stage("acceptance", len(fresh) + 1, "waiting", "baseline_awaiting_human")
    if any(now - item["createdAt"] > ACCEPTANCE_WAIT_SECONDS for item in fresh):
        return stage("acceptance", len(fresh), "waiting", "acceptance_overdue")
    return stage("acceptance", len(fresh), "ok", "awaiting_human_within_window" if fresh else "nothing_to_accept")


def claim_stage(claims):
    ready = [item for item in claims if item["status"] == "ready"]
    if any(item["blockReason"] == "budget_exhausted" for item in claims):
        return stage("claim", len(ready), "blocking", "budget_exhausted")
    return stage("claim", len(ready), "ok", "cards_ready" if ready else "nothing_ready")


def work_stage(latest, now):
    running = [item for item in latest if item["state"] == "running"]
    expired = [item for item in running if item["deadline"] <= now]
    if expired:
        return stage("work", len(running) - len(expired), "blocking", "lease_past_deadline")
    return stage("work", len(running), "ok", "runs_active" if running else "no_active_runs")


def evidence_stage(reported, accepted):
    if any(item["acceptedRevision"] != accepted for item in reported):
        return stage("evidence", len(reported), "waiting", "stale_evidence")
    return stage("evidence", len(reported), "ok", "evidence_reported" if reported else "no_evidence")


def review_stage(pending_review):
    if pending_review:
        return stage("review", len(pending_review), "waiting", "human_review_required")
    return stage("review", 0, "ok", "nothing_to_review")


def pull_stages(reported, pulls):
    if pulls is None:
        return [stage(name, 0, "not_connected", "pull_request_link_module_missing")
                for name in ("pull_request", "merge", "plan_writeback")]
    linked = {item["executionId"] for item in pulls}
    unlinked = [item for item in reported if item["id"] not in linked]
    pull = (stage("pull_request", len(linked), "blocking", "results_without_pull_request") if unlinked
            else stage("pull_request", len(linked), "ok", "results_linked" if linked else "no_pull_requests"))
    merged = [item for item in pulls if item["state"] == "merged"]
    opened = [item for item in pulls if item["state"] == "open"]
    merge = (stage("merge", len(merged), "waiting", "pull_requests_open") if opened
             else stage("merge", len(merged), "ok", "merged" if merged else "nothing_to_merge"))
    written = [item for item in merged if item.get("planWrittenBack") is True]
    if merged and not any("planWrittenBack" in item for item in pulls):
        back = stage("plan_writeback", 0, "not_connected", "writeback_not_reported")
    elif len(written) < len(merged):
        back = stage("plan_writeback", len(written), "waiting", "merged_without_plan_writeback")
    else:
        back = stage("plan_writeback", len(written), "ok", "plan_written_back" if written else "nothing_to_write_back")
    return [pull, merge, back]
