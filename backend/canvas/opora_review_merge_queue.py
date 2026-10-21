"""Merge-queue semantics of the gate (docs/oporahub-review-jobs.md, "Fronta merge").

`ready` needs the required CI checks passed on the current head AND that head based on the
CURRENT base branch head (merge-base == base tip, read via the GET-only compare API). A head
behind its base is `stale_against_main` with the agent action `pr.update_branch`. Observations
are taken at review sync outside every lock, throttled per PR, and age out after a limit."""
import time

from backend.canvas.opora_review_checks import observed_checks
from backend.canvas.opora_review_gate_config import rules
from backend.canvas.opora_review_template import missing_sections
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_review_gate_facts import ReviewGateFacts


def _needed(config):
    gate = rules(config)
    return gate["mergeQueue"]["enabled"] or bool(gate["template"]["sections"])


def base_reader(service):
    reader = getattr(service, "base_reader", None)
    if reader is None:
        from backend.integrations.github_pr_base_reader import GitHubPullRequestBaseReader
        reader = service.base_reader = GitHubPullRequestBaseReader()
    return reader


def observe_bases(service, project, workspace, config, now=None):
    """Refresh the base/template observation of open linked PRs whose observation is missing,
    for another head, or older than `observe_interval_seconds`. Returns the observed PR keys."""
    if not _needed(config):
        return []
    interval = rules(config)["mergeQueue"]["observeIntervalSeconds"]
    now = service.clock() if now is None else now
    with service.transaction(project, workspace) as store:
        facts = ReviewGateFacts(store.db, project, workspace)
        due = []
        for link in ExecutionPullRequests(store.db, project, workspace).listing():
            if link["state"] != "open":
                continue
            seen = facts.base_observation(link["repository"], link["number"])
            if seen is None or seen["headSha"] != link["head_sha"] or now - seen["observedAt"] >= interval:
                due.append(link)
    observed = []
    for link in due:
        if link["enrollment"] == "unavailable":  # Project without GitHub: never touch the network.
            observed.append((link, {"complete": False, "error": "github-unavailable"}))
            continue
        try:
            observed.append((link, base_reader(service).base(link["repository"], link["number"], link["head_sha"])))
        except Exception:  # noqa: BLE001 - any reader failure leaves the head unobserved (fail closed)
            observed.append((link, {"complete": False, "error": "github-unavailable"}))
    if not observed:
        return []
    with service.transaction(project, workspace) as store:
        facts, links = ReviewGateFacts(store.db, project, workspace), ExecutionPullRequests(store.db, project, workspace)
        for link, observation in observed:
            current = links.read(link["execution_id"])
            if current is not None and current["head_sha"] == link["head_sha"]:
                facts.save_base_observation(link["repository"], link["number"], link["head_sha"], observation, now)
    return [(link["repository"], link["number"]) for link, _ in observed]


def head_snapshot(evidence, repository, number, head):
    """Newest complete GitHub evidence snapshot of exactly this head (same filter as approvals)."""
    for snapshot in evidence or []:
        if (snapshot.get("prNumber") == number
                and str((snapshot.get("repository") or {}).get("fullName", "")).casefold() == repository
                and snapshot.get("complete") is True and (snapshot.get("pr") or {}).get("headSha") == head):
            return snapshot
    return None


def required_checks(snapshot, names, head):
    """`{name: passed|failed|pending|missing|unknown}` of the latest check run or status per name at head."""
    result = {}
    for name in names:
        if snapshot is None:
            result[name] = "missing"
            continue
        checks = [item for item in snapshot.get("checks", []) if isinstance(item, dict) and item.get("name") == name]
        statuses = [item for item in snapshot.get("statuses", []) if isinstance(item, dict) and item.get("context") == name]
        observed = observed_checks({"checks": checks, "statuses": statuses}, head)
        result[name] = "missing" if observed["observedCount"] == 0 and observed["status"] == "unknown" else observed["status"]
    return result


def evaluate(facts, link, evidence, config, now=None):
    """(reasons, details) of the merge-queue and template rules for the link's current head."""
    gate, reasons, details = rules(config), [], {}
    if not _needed(config):
        return reasons, details
    now = time.time() if now is None else now
    head = link["head_sha"]
    seen = facts.base_observation(link["repository"], link["number"])
    current = seen if seen is not None and seen["headSha"] == head and seen.get("complete") is True else None
    queue = gate["mergeQueue"]
    if queue["enabled"]:
        names = queue["requiredChecks"]
        states = required_checks(head_snapshot(evidence, link["repository"], link["number"], head), names, head)
        if any(state == "failed" for state in states.values()):
            reasons.append("required_checks_failed")
        elif any(state != "passed" for state in states.values()):
            reasons.append("required_checks_pending")
        fresh_enough = current is not None and now - current["observedAt"] <= queue["maxAgeSeconds"]
        if not fresh_enough:
            reasons.append("base_freshness_unobserved")
        elif current["behindBy"] > 0 or current["mergeBaseSha"] != current["baseSha"]:
            reasons.append("stale_against_main")
        details["requiredChecks"] = states
        details["base"] = None if current is None else {
            "baseRef": current["baseRef"], "baseSha": current["baseSha"], "mergeBaseSha": current["mergeBaseSha"],
            "behindBy": current["behindBy"], "observedAt": current["observedAt"], "fresh": fresh_enough}
    sections = gate["template"]["sections"]
    if sections:
        if current is None:
            reasons.append("template_unobserved")
            details["template"] = {"missing": None}
        else:
            missing = missing_sections(current["sections"], sections)
            if missing:
                reasons.append("template_incomplete")
            details["template"] = {"missing": missing}
    return reasons, details
