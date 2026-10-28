"""Open guard findings in agent-state: `guards` + `cards[].guardFindings` (docs/strazci.md §5).

Read-only over the `guard_findings` table the guard worker writes. Findings of the `mapa` guard are left out:
map holes already reach agents as `mapGaps` (one source of map holes), so nobody sees the same hole twice. The same
holds for `journey.failed` / `journey.stale` of the `cesty` guard (map check reports them as `journey.unverified`).
Only findings of the requested workspace count (`workspaceId` of the finding, default `draft`).

- `guards` = `{open: {block, warn, info}, findings: [top LIMIT open findings, block first]}`; a finding is
  `{key, guard, rule, severity, message, nodeId?, journeyId?, executionId?, workspaceId, firstSeen, lastSeen}`.
- a card with at least one open finding gets `guardFindings: {count, severity}` (highest severity).
"""
from database.repositories.guard_findings import GuardFindings

LIMIT = 20
EXCLUDED = frozenset({"mapa"})
EXCLUDED_RULES = frozenset({"journey.failed", "journey.stale"})
SEVERITIES = ("block", "warn", "info")
KEYS = ("key", "guard", "rule", "severity", "message", "nodeId", "journeyId", "executionId", "firstSeen", "lastSeen")


def open_findings(db, project, workspace):
    """Open findings of the workspace without the map guard, in table order (block first, newest first)."""
    rows = GuardFindings(db, project).list(open_only=True, limit=100_000)
    return [row for row in rows if row["guard"] not in EXCLUDED and row["rule"] not in EXCLUDED_RULES and (row.get("workspaceId") or "draft") == workspace]


def summary(findings):
    """The `guards` block of agent-state."""
    return {"open": {severity: sum(item["severity"] == severity for item in findings) for severity in SEVERITIES},
            "findings": [{**{key: item[key] for key in KEYS if item.get(key) is not None},
                          "workspaceId": item.get("workspaceId") or "draft"} for item in findings[:LIMIT]]}


def by_card(findings):
    """{nodeId: {count, severity}} over open findings that name a card."""
    result = {}
    for item in findings:
        if not item.get("nodeId"):
            continue
        current = result.setdefault(item["nodeId"], {"count": 0, "severity": item["severity"]})
        current["count"] += 1
        if SEVERITIES.index(item["severity"]) < SEVERITIES.index(current["severity"]):
            current["severity"] = item["severity"]
    return result


def attach(entries, counts):
    """Cards of agent-state with `guardFindings` where a guard has an open finding."""
    return [{**entry, "guardFindings": counts[entry["nodeId"]]} if entry["nodeId"] in counts else entry
            for entry in entries]


def node_findings(db, project, workspace, node, limit=3):
    """node-brief `guards`: `[{rule, message}]`, at most `limit` open findings of one card (map guard left out)."""
    return [{"rule": item["rule"], "message": item["message"]}
            for item in open_findings(db, project, workspace) if item.get("nodeId") == node][:limit]
