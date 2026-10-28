"""Map holes as agent work in agent-state: `mapGaps` + `mapGapsTotal` (docs/architektura-pro-agenty.md §5.1).

One map check per agent-state build, over the project's accepted architecture with the latest journey runs
(the same input as `GET /api/project-architecture/map-check`). Every finding becomes
`{rule, message, nodeId, journeyId?, edgeId?, owner}` in map-check order; `nodeId` is the card where the hole
is solved (`check_map(locate=True)` → `solverId`), `owner` is "human" for `page.no-goal` and `journey.broken`,
"agent" otherwise. Capped at `LIMIT` items; nothing is written, a hole disappears once the check stops reporting it.

Worktrees (docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §4) come from the single source
`map_check_worktrees.worktree_overlay`: read in worktree `w`, a hole closed in `w` is left out (the agent there
already fixed it), a hole closed in another worktree carries `inProgress: {workspaceId, branch, actor}` (not to be
taken), and holes `w` opened come first with `origin: "worktree"`. On `main` / `draft` only `inProgress` applies.
`mapGapsTotal` counts the result. The `trend` guard keeps counting main only (`all_items`).
"""
from backend.project.architecture import map_check_worktrees as overlay
from backend.project.architecture.journey_runs import latest_journey_runs
from backend.project.architecture.map_check import check_map, finding_key
from backend.project.architecture.work_status import architecture_graph

LIMIT = 50
HUMAN_RULES = frozenset({"page.no-goal", "journey.broken"})


def _item(finding, **extra):
    return {"rule": finding["rule"], "message": finding["message"], "nodeId": finding["solverId"],
            **{key: finding[key] for key in ("journeyId", "edgeId") if key in finding},
            "owner": "human" if finding["rule"] in HUMAN_RULES else "agent", **extra}


def items(findings):
    """agent-state items from located map-check findings, in their order."""
    return [_item(f) for f in findings if f.get("solverId")]


def all_items(canvas, project):
    """Every map hole of main as an agent-state item, uncapped (the `trend` guard counts them, docs/strazci.md §4)."""
    graph = architecture_graph(canvas, project)
    return items(check_map(graph, latest_journey_runs(canvas, project), locate=True)["findings"])


def workspace_items(state, workspace):
    """agent-state items of `workspace` from a `worktree_overlay` result."""
    own = next((tree for tree in state["worktrees"] if tree["workspaceId"] == workspace), None)
    fixed = set(own["closed"]) if own else set()
    working = {}
    for tree in state["worktrees"]:
        if tree is not own:
            for key in tree["closed"]:
                working.setdefault(key, {"workspaceId": tree["workspaceId"], "branch": tree["branch"],
                                         "actor": tree["actor"]})
    opened = [_item(f, origin="worktree") for f in (own["opened"] if own else []) if f.get("solverId")]
    main = []
    for finding in state["main"]:
        key = finding_key(finding)
        if not finding.get("solverId") or key in fixed:
            continue
        main.append(_item(finding, **({"inProgress": dict(working[key])} if key in working else {})))
    return [*opened, *main]


def read(canvas, project, workspace):
    """(mapGaps capped at LIMIT, mapGapsTotal). Inside `steady_reads` the accepted view is computed once."""
    work = workspace_items(overlay.worktree_overlay(canvas, project), workspace)
    return work[:LIMIT], len(work)
