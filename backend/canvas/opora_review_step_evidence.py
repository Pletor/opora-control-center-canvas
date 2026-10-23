"""Per-step evidence on a merge gate item (`evidence.steps`, docs/oporahub-review-jobs.md, "Doklady kroků").

For every step pinned in the assignment snapshot of the linked PR's execution, the gate shows what
the runs reported: `status` done / blocked (failed or skipped) / missing (never reported), and the
`evidence` {checks, commits, notes} of the newest report from the final `result.stepResults` or a
step checkpoint (`POST /executions/{id}/steps`). Reports of earlier runs of the same card count
while their pinned step is identical; a `done` report sticks (same rule as opora_step_results).
`verdict` flags steps that are not done and steps without any evidence. Deterministic, read-only and
NEVER a gate reason: the gate status is unchanged, like the PR Lens and the design preview."""
from backend.canvas.graph import digest
from backend.canvas.opora_plan_steps import ordered, topological
from database.repositories.opora_executions import Executions

STATUS = {"done": "done", "failed": "blocked", "skipped": "blocked"}


def _evidence(item):
    raw = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    return {"checks": list(raw.get("checks") or []), "commits": list(raw.get("commits") or []),
            "notes": raw.get("notes") if isinstance(raw.get("notes"), str) else ""}


def _evidenced(evidence):
    return bool(evidence["checks"] or evidence["commits"] or evidence["notes"].strip())


def _reports(repo, node, pinned):
    """`{stepId: (item, executionId, source, at)}`: newest report per pinned step, a `done` one sticks."""
    want, found = {key: digest(value) for key, value in pinned.items()}, {}
    for record in repo.history(node):  # newest execution first
        own = {item["id"]: digest(item) for item in (record.get("assignment") or {}).get("steps") or []}
        reported = [(item, "result", receipt.get("createdAt"))
                    for receipt in reversed(repo.receipts(record["executionId"]))
                    for item in (receipt.get("result") or {}).get("stepResults") or []]
        reported += [(item, "checkpoint", item.get("createdAt")) for item in reversed(repo.steps(record["executionId"]))]
        for item, source, at in reported:
            step = item.get("stepId")
            if step not in want or own.get(step) != want[step]:
                continue
            if step not in found or (item.get("status") == "done" and found[step][0].get("status") != "done"):
                found[step] = (item, record["executionId"], source, at)
    return found


def for_link(db, project, workspace, link):
    """`{items, verdict, decisions}` for the linked execution, or None when it pinned no steps."""
    repo = Executions(db, project, workspace)
    try:
        record = repo.read(link["execution_id"])
    except ValueError:  # a link to a vanished execution shows no steps
        return None
    steps = (record.get("assignment") or {}).get("steps") or []
    if not steps:
        return None
    pinned = {item["id"]: item for item in steps}
    found = _reports(repo, record["nodeId"], pinned)
    items = []
    for step in topological(steps) or [item["id"] for item in ordered(steps)]:
        item, execution, source, at = found.get(step, ({}, None, None, None))
        evidence = _evidence(item) if item else {"checks": [], "commits": [], "notes": ""}
        items.append({"id": step, "title": pinned[step].get("title", ""), "status": STATUS.get(item.get("status"), "missing"),
                      "reported": item.get("status"), "executionId": execution, "source": source, "at": at,
                      "evidence": evidence, "evidenced": _evidenced(evidence)})
    blocked = [item["id"] for item in items if item["status"] == "blocked"]
    missing = [item["id"] for item in items if item["status"] == "missing"]
    without = [item["id"] for item in items if not item["evidenced"]]
    decisions = sum(len((receipt.get("result") or {}).get("decisions") or [])
                    for receipt in repo.receipts(record["executionId"]))
    return {"items": items, "decisions": decisions, "verdict": {
        "status": "evidenced" if not (blocked or missing or without) else "incomplete", "total": len(items),
        "done": len(items) - len(blocked) - len(missing), "blocked": blocked, "missing": missing,
        "withoutEvidence": without}}
