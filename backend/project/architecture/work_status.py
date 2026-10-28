"""Stav práce na worktree a doménách (docs/domeny-a-worktree.md §7, §9).

Čisté funkce nad už načtenými zdroji (relace asistenta, lease a aktivita karet)
s vloženým `now`; čtení zdrojů je odděleně v `collect_sources` a `work_status`.
Chybějící relace není „stojí“: worktree bez jakéhokoli signálu je „bez relace“.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

CARD_ACTIVITY_SECONDS = 300    # aktivita karty mladší než toto = práce běží
STOPPED_WINDOW_SECONDS = 24 * 3600  # prošlá lease s čerstvější aktivitou = stojí

RUNNING, WAITING, STOPPED, NONE = "running", "waiting", "stopped", "none"
RANK = {NONE: 0, STOPPED: 1, WAITING: 2, RUNNING: 3}
MAIN_WORKSPACES = ("main", "draft")


def parse_time(value):
    """ISO čas (i s „Z“, i bez zóny = UTC) → datetime; neplatná hodnota → None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _age(value, now):
    moment = parse_time(value)
    return None if moment is None else (now - moment).total_seconds()


def _assistant_signal(session):
    state = session.get("state")
    if state == "running":
        return RUNNING, "asistent běží"
    if state == "waiting_approval":
        return WAITING, "asistent čeká na schválení"
    if state == "idle":
        return WAITING, "asistent čeká na zprávu"
    if state == "error":
        return STOPPED, "asistent skončil chybou"
    return None


def _lease_signal(lease, activity, now):
    idle = _age(activity.get("updated_at"), now) if activity else None
    if lease["expires_at"] > now.timestamp():
        if idle is not None and idle <= CARD_ACTIVITY_SECONDS:
            return RUNNING, "karta má čerstvou aktivitu"
        return WAITING, "karta převzata bez nedávné aktivity"
    if idle is not None and idle <= STOPPED_WINDOW_SECONDS:
        return STOPPED, "převzetí karty vypršelo"
    return None


def worktree_state(sessions, leases, activity, now):
    """Stav jednoho worktree: nejvyšší signál ze všech zdrojů; `reasons` jen od vítězného stavu.

    `activity` je slovník node_id → řádek `card_work_activity`."""
    signals = [_assistant_signal(item) for item in sessions]
    signals += [_lease_signal(lease, activity.get(lease["node_id"]), now) for lease in leases]
    signals = [signal for signal in signals if signal]
    if not signals:
        return NONE, []
    best = max(RANK[state] for state, _ in signals)
    state = next(name for name, rank in RANK.items() if rank == best)
    return state, [reason for sig, reason in signals if sig == state]


def _session_view(source, item_id, state, node_id, last_seen):
    return {"source": source, "id": item_id, "state": state, "nodeId": node_id, "lastSeenAt": last_seen}


def _worktree_entry(workspace, sources, now, card_name):
    wid = workspace["id"]
    sessions = [s for s in sources["sessions"] if s.get("workspace") == wid]
    leases = [lease for lease in sources["leases"] if lease["workspace_id"] == wid]
    activity = {a["node_id"]: a for a in sources["activity"] if a["workspace_id"] == wid}
    state, reasons = worktree_state(sessions, leases, activity, now)
    views = ([_session_view("assistant", s["id"], s["state"], s.get("nodeId"), s.get("updatedAt")) for s in sessions]
             + [_session_view("lease", f"{lease['workspace_id']}:{lease['node_id']}",
                              "active" if lease["expires_at"] > now.timestamp() else "expired",
                              lease["node_id"], (activity.get(lease["node_id"]) or {}).get("updated_at"))
                for lease in leases])
    card_ids = []
    for node_id in [s.get("nodeId") for s in sessions] + [lease["node_id"] for lease in leases]:
        if node_id and node_id not in card_ids:
            card_ids.append(node_id)
    entry = {"id": wid, "branch": workspace.get("branch"), "actor": workspace.get("actor"),
             "state": state, "reasons": reasons, "sessions": views,
             "cards": [{"nodeId": node_id, "name": card_name(wid, node_id)} for node_id in card_ids]}
    if workspace.get("created_at"):
        entry["createdAt"] = workspace["created_at"]
    return entry


def _counts(worktrees):
    counts = {RUNNING: 0, WAITING: 0, STOPPED: 0, NONE: 0}
    for item in worktrees:
        counts[item["state"]] += 1
    return {**counts, "total": len(worktrees)}


def compose_work_status(domains, workspaces, sources, now, card_name=lambda wid, node_id: node_id):
    """`domains`: [{id, name, environment}] z architektury; `workspaces`: řádky worktree s `node_id`."""
    known = {domain["id"] for domain in domains}
    entries = [(w.get("node_id"), _worktree_entry(w, sources, now, card_name)) for w in workspaces]
    result = []
    for domain in domains:
        worktrees = [entry for node_id, entry in entries if node_id == domain["id"]]
        result.append({"id": domain["id"], "name": domain["name"], "environment": domain["environment"],
                       "counts": _counts(worktrees), "worktrees": worktrees})
    main = [_session_view("assistant", s["id"], s["state"], s.get("nodeId"), s.get("updatedAt"))
            for s in sources["sessions"] if s.get("workspace") in MAIN_WORKSPACES]
    return {"domains": result, "unassigned": [entry for node_id, entry in entries if node_id not in known],
            "mainSessions": main}


def accepted_workspace(service, project):
    """Prostor přijatého grafu: `main` u Git projektu, jinak `draft`."""
    return "main" if service.project_hub.settings(project)["project"]["sourceKind"] == "git" else "draft"


def architecture_graph(service, project):
    """Přijatý graf projektu (architektura složená s obsahem `main`, u projektu bez Gitu `draft`).

    Jediné místo, které ví, odkud se architektura s komponentami pod stránkami čte."""
    return service.view(project, accepted_workspace(service, project))["graph"]


def architecture_domains(service, project):
    """Domény projektu = uzly `site.kind == "application"`."""
    domains = []
    for node in architecture_graph(service, project)["nodes"]:
        site = node.get("site")
        if isinstance(site, dict) and site.get("kind") == "application":
            environment = (site.get("environments") or [{}])[0]
            domains.append({"id": node["id"], "name": node.get("name") or node["id"],
                            "environment": {"name": environment.get("name"), "host": environment.get("host")}})
    return domains


def collect_sources(service, registry, project):
    with service.reading(project):
        db = service.db_for(project)
        leases = [dict(r) for r in db.execute(
            "SELECT workspace_id,node_id,owner,expires_at FROM card_leases WHERE project_id=?", (project,))]
        activity = [dict(r) for r in db.execute(
            "SELECT workspace_id,node_id,agent,updated_at FROM card_work_activity WHERE project_id=?", (project,))]
    return {"sessions": registry.list(project), "leases": leases, "activity": activity}


def work_status(service, registry, project, now=None):
    now = now or datetime.fromtimestamp(time.time(), UTC)
    domains = architecture_domains(service, project)
    sources = collect_sources(service, registry, project)
    names = {}

    def card_name(wid, node_id):
        if wid not in names:
            try:
                names[wid] = {n["id"]: n.get("name") for n in service.view(project, wid)["graph"]["nodes"]}
            except (ValueError, KeyError, OSError):
                names[wid] = {}
        return names[wid].get(node_id) or node_id

    return compose_work_status(domains, service.workspaces(project), sources, now, card_name)
