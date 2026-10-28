"""Map holes as agent work in agent-state: `mapGaps` + `mapGapsTotal` (docs/architektura-pro-agenty.md §5.1).

One map check per agent-state build, over the project's accepted architecture with the latest journey runs
(the same input as `GET /api/project-architecture/map-check`). Every finding becomes
`{rule, message, nodeId, journeyId?, edgeId?, owner}` in map-check order; `nodeId` is the card where the hole
is solved (`check_map(locate=True)` → `solverId`), `owner` is "human" for `page.no-goal` and `journey.broken`,
"agent" otherwise. Capped at `LIMIT` items; nothing is written, a hole disappears once the check stops reporting it.
"""
from backend.project.architecture.journey_runs import latest_journey_runs
from backend.project.architecture.map_check import check_map
from backend.project.architecture.work_status import architecture_graph

LIMIT = 50
HUMAN_RULES = frozenset({"page.no-goal", "journey.broken"})


def items(findings):
    """agent-state items from located map-check findings, in their order."""
    return [{"rule": f["rule"], "message": f["message"], "nodeId": f["solverId"],
             **{key: f[key] for key in ("journeyId", "edgeId") if key in f},
             "owner": "human" if f["rule"] in HUMAN_RULES else "agent"}
            for f in findings if f.get("solverId")]


def all_items(canvas, project):
    """Every map hole as an agent-state item, uncapped (the `trend` guard counts them, docs/strazci.md §4)."""
    graph = architecture_graph(canvas, project)
    return items(check_map(graph, latest_journey_runs(canvas, project), locate=True)["findings"])


def read(canvas, project):
    """(mapGaps capped at LIMIT, mapGapsTotal). Inside `steady_reads` the accepted view is computed once."""
    work = all_items(canvas, project)
    return work[:LIMIT], len(work)
