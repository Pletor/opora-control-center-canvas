"""Kontrola mapy přes worktree (`docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md` §3).

Jediné místo, které skládá kontrolu mapy přes aktivní worktree; agent-state, velín i Studio čtou jeho výsledek.
Pravda je `main`: `main` = nálezy přijatého grafu (`architecture_graph`) s doklady cest. Každý aktivní worktree
(řádek `workspaces` Git projektu mimo `main`, archivované `service.workspaces` vynechává) se kontroluje nad svým
pohledem `service.view(project, wid)` bez dokladů (`runs=None`): `journey.unverified` se ve worktree nehodnotí,
a proto se z `main` při porovnání vynechává (worktree ho nikdy nezavře ani neotevře).

- `closed` = klíče nálezů `main`, které ve worktree nejsou (agent je tam zalepil);
- `opened` = nálezy worktree, které na `main` nejsou, v pořadí kontroly, nejvýš `OPENED_LIMIT`.

Klíč nálezu je `map_check.finding_key` (tentýž jako dávka plánu). Nálezy worktree se drží v paměti procesu podle
`(project, wid, digest pohledu)`: nezměněný worktree se znovu nekontroluje. Worktree, jehož pohled nejde přečíst
(chybí složka, Git selže), se vynechá. Nic se nezapisuje, model se nevolá.
"""

import threading

from backend.project.architecture.journey_runs import latest_journey_runs
from backend.project.architecture.map_check import check_map, finding_key
from backend.project.architecture.work_status import (
    MAIN_WORKSPACES,
    accepted_workspace,
    architecture_graph,
)

OPENED_LIMIT = 50
UNJUDGED = "journey.unverified"  # doklady cest jsou projektové, ve worktree se nehodnotí

_cache = {}  # (project, wid) -> (digest pohledu, nálezy)
_cache_lock = threading.Lock()


def _worktree_findings(service, project, wid):
    view = service.view(project, wid)
    stamp = view.get("digest")
    with _cache_lock:
        hit = _cache.get((project, wid))
    if stamp is not None and hit is not None and hit[0] == stamp:
        return hit[1]
    findings = check_map(view["graph"], None, locate=True)["findings"]
    if stamp is not None:
        with _cache_lock:
            _cache[(project, wid)] = (stamp, findings)
    return findings


def _entry(workspace, main_keys, findings):
    """Řádek worktree; `main_keys` = klíče nálezů `main` v pořadí kontroly."""
    keys, known = {finding_key(finding) for finding in findings}, set(main_keys)
    return {"workspaceId": workspace["id"], "branch": workspace.get("branch"), "actor": workspace.get("actor"),
            "domainId": workspace.get("node_id"),
            "closed": [key for key in main_keys if key not in keys],
            "opened": [dict(finding) for finding in findings if finding_key(finding) not in known][:OPENED_LIMIT]}


def worktree_overlay(service, project):
    """`{main: [nález…], worktrees: [{workspaceId, branch, actor, domainId, closed: [klíč…], opened: [nález…]}]}`."""
    main = check_map(architecture_graph(service, project), latest_journey_runs(service, project), locate=True)["findings"]
    if accepted_workspace(service, project) != "main":
        return {"main": main, "worktrees": []}
    main_keys = list(dict.fromkeys(finding_key(finding) for finding in main if finding["rule"] != UNJUDGED))
    worktrees = []
    for workspace in service.workspaces(project):
        if workspace["id"] in MAIN_WORKSPACES:
            continue
        try:
            findings = _worktree_findings(service, project, workspace["id"])
        except (ValueError, KeyError, OSError):
            continue
        worktrees.append(_entry(workspace, main_keys, findings))
    return {"main": main, "worktrees": worktrees}
