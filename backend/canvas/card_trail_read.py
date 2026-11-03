"""Sběr faktů pro stopu práce karty (docs/stopa-prace-karty.md): jen čtení existujících záznamů, ohraničeně.

Čte běhy exekucí karty s výsledky a průběžnými kroky, tickety práce karty, události karty, záznam činnosti, vazby
z karty se zprávami, PR a `dod.missing`; soubory commitů z `git show --name-only` v repozitáři projektu
(když ho server zná). Nic nezapisuje, schéma beze změny, model nevolá. Projekci dělá `card_trail.project_trail`.
"""
import re
import sqlite3

from backend.canvas.graph import valid_id
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_execution_results import ExecutionResults
from backend.integrations import git_read
from backend.project.workspace.workspace_sources import WorkspaceSources
from database.repositories import opora_events as events_store
from database.repositories.tickets import TicketStore

RUNS = 10
TICKETS = 10
EVENTS = 200
ACTIVITY = 200
COMMITS = 20
SHA = re.compile(r"[a-f0-9]{7,40}")


def _runs(service, project, workspace, node):
    """Běhy karty (nejnovější první) se stavem jako v historii exekucí, výsledky a průběžnými kroky; bez tokenu."""
    executions = ExecutionResults(service)
    with executions.transaction(project, workspace) as repo:
        found = []
        for record in repo.history(node)[:RUNS]:
            state = executions.response(repo, record)["state"]
            public = {key: value for key, value in record.items() if key != "token"} | {"state": state}
            found.append({"record": public, "receipts": repo.receipts(record["executionId"]),
                          "checkpoints": repo.steps(record["executionId"])})
        events = events_store.latest_for_node(repo.db, project, workspace, node, EVENTS)
        tickets = TicketStore(repo.db, project).for_card(workspace, node, TICKETS)
    return found, tickets, events


def _activity(service, project, workspace, node):
    from backend.canvas.activity_log import ActivityLog

    return ActivityLog(service).list(project=project, workspace=workspace, node_id=node, limit=ACTIVITY)["entries"]


def _graph(service, project, workspace):
    """Vazby, názvy karet a zprávy na vazbách (`state.edges`)."""
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

    graph = service.view(project, workspace)["graph"]
    state = (getattr(service, "desktop_v3_state", None) or DesktopV3State(service)).read(project, workspace)["state"]
    names = {item["id"]: item.get("name") or item["id"] for item in graph["nodes"]}
    return graph["edges"], names, state.get("edges") or {}


def _pr_and_missing(service, project, workspace, node):
    from backend.canvas import opora_agent_state_pulls as pulls
    from backend.canvas import opora_card_done as card_done
    from backend.canvas.opora_execution_deliver import done_state

    link = card_done.link_for(pulls.read(service, project, workspace), node)
    number = (link or {}).get("number")
    pr = {"number": number if type(number) is int else None, "state": link["state"]} if link else None
    state = done_state(service, project, workspace, node)
    return pr, (state["missing"] if state is not None else ["steps"]), state


def repo_root(service, project, workspace):
    """Kořen repozitáře prostoru (zdroj prostoru, jinak složka projektu), nebo None."""
    from backend.canvas.opora_local_merge import repository_path

    try:
        root = WorkspaceSources(service).root(project, workspace)
    except (ValueError, KeyError, OSError, sqlite3.Error):
        root = None
    if root is not None:
        return str(root)
    try:
        return repository_path(service, project)
    except (ValueError, KeyError, OSError, sqlite3.Error):
        return None


def commit_shas(runs, tickets):
    found = []
    for run in runs:
        for receipt in run["receipts"]:
            for item in (receipt.get("result") or {}).get("stepResults") or []:
                found += ((item.get("evidence") or {}).get("commits") or []) if isinstance(item, dict) else []
        for item in run["checkpoints"]:
            found += (item.get("evidence") or {}).get("commits") or [] if isinstance(item, dict) else []
    found += [(ticket.get("delivery") or {}).get("sha") for ticket in tickets]
    unique = []
    for sha in found:
        if isinstance(sha, str) and SHA.fullmatch(sha) and sha not in unique:
            unique.append(sha)
    return unique[:COMMITS]


def commit_files(root, shas):
    """`{sha: [cesta]}` nebo None, když repozitář není známý (pole `files` se pak vynechá)."""
    if not root:
        return None
    return {sha: git_read.changed_paths(root, sha) for sha in shas}


def gather(service, project, workspace, node):
    """Syrová fakta jedné karty pro `card_trail.project_trail`."""
    scope({"project": project, "workspace": workspace})
    if not valid_id(node):
        raise ValueError("Neplatné nodeId.")
    runs, tickets, events = _runs(service, project, workspace, node)
    edges, names, reports = _graph(service, project, workspace)
    pr, missing, state = _pr_and_missing(service, project, workspace, node)
    shas = commit_shas(runs, tickets)
    files = commit_files(repo_root(service, project, workspace), shas)
    return {"nodeId": node, "runs": runs, "tickets": tickets, "events": events,
            "activity": _activity(service, project, workspace, node), "edges": edges, "names": names,
            "reports": reports, "pr": pr, "missing": missing, "files": files,
            "afterMerge": {key: state[key] for key in ("afterMerge", "afterMergeEvidence")} if state and "afterMerge" in state else None}
