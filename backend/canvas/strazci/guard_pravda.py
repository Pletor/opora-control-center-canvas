"""Strážce `pravda` (`docs/strazci.md` §4): synchronizace worktree s `main` a návrhy, které leží u člověka.

Jen čte a hlásí, bez sítě (žádný fetch, jen lokální Git s krátkým timeoutem):
- `truth.worktree-behind` (warn): větev worktree (`workspaces.branch`, `work/<id>`) je za hlavní větví projektu
  (`projects.branch`, bez ní HEAD hlavního stromu) o víc než `BEHIND_LIMIT` commitů; počítá
  `git rev-list --count <worktree>..<main>` v repozitáři projektu. Worktree patří doméně
  (`docs/domeny-a-worktree.md`), proto `nodeId` = doména worktree. Klíč `truth:worktree-behind:<worktree>`.
  Nečitelná větev (smazaná, Git selže nebo nestihne) se přeskočí, nález se nevymýšlí.
- `truth.proposal-stale` (warn): návrh zadání, grafu (přidání i změna) nebo obsahu čeká na rozhodnutí člověka
  déle než `PROPOSAL_HOURS` h. „Čeká na člověka“ = jako rozhodnutí v agent-state (`opora_agent_state.proposals`):
  nepřijatý, nenahrazený novějším a postavený na aktuální přijaté revizi (zastaralý návrh přenáší agent, ne člověk).
  Klíč `truth:proposal-stale:<prostor>:<id>`.
"""
import subprocess

from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.strazci.guard_mapa import workspace_of, workspaces_of
from backend.canvas.strazci.registry import Guard
from backend.integrations.gitio import git
from backend.project.architecture.work_status import parse_time

BEHIND_LIMIT = 20
PROPOSAL_HOURS = 24
GIT_TIMEOUT = 10
KINDS = {"graph-additions": "graf", "graph-changes": "změna grafu", "content-proposal": "obsah"}


def epoch(value):
    """ISO čas (bez zóny = UTC) → epoch sekundy; nečitelný = None."""
    moment = parse_time(value)
    return None if moment is None else moment.timestamp()


def behind_count(repo, branch, main):
    """Kolik commitů `main` větev `branch` nemá; None, když to lokální Git neřekne."""
    try:
        value = git(repo, "rev-list", "--count", f"{branch}..{main}", timeout=GIT_TIMEOUT, optional=True)
    except (OSError, ValueError, subprocess.TimeoutExpired):  # chybějící git i timeout = bez nálezu
        return None
    return int(value) if value and value.isdigit() else None


def read_worktrees(service, project):
    """`[{id, branch, nodeId, behind}]` worktree projektu z Gitu; jiný projekt = prázdný seznam."""
    if workspace_of(service, project) != "main":
        return []
    row = service.row("projects", project)
    main = row.get("branch") or "HEAD"
    result = []
    for workspace in service.workspaces(project):
        if not workspace.get("branch"):
            continue
        result.append({"id": workspace["id"], "branch": workspace["branch"], "nodeId": workspace.get("node_id"),
                       "behind": behind_count(row["repo"], workspace["branch"], main), "main": main})
    return result


def worktree_findings(worktrees):
    findings = []
    for item in worktrees:
        if item["behind"] is None or item["behind"] <= BEHIND_LIMIT:
            continue
        findings.append({"key": f"truth:worktree-behind:{item['id']}", "rule": "truth.worktree-behind",
                         "severity": "warn", "workspaceId": item["id"],
                         **({"nodeId": item["nodeId"]} if item.get("nodeId") else {}),
                         "message": f"Worktree {item['branch']} je {item['behind']} commitů za {item['main']}.",
                         "data": {"behind": item["behind"], "branch": item["branch"]}})
    return findings


def read_proposals(service, project):
    """Návrhy čekající na člověka: `[{workspaceId, id, kind, subject, createdAt}]` (createdAt v epoch s)."""
    result = []
    for workspace in workspaces_of(service, project):
        with service.graph_lock_for(project), service.lock_for(project), service.steady_reads(project):
            changesets = OporaChangesets(service).list(project, workspace)
            families = [changesets["items"], OporaGraphProposals(service).list(project, workspace)["items"],
                        OporaContentChanges(service).list(project, workspace)["items"]]
        accepted = changesets["acceptedHead"]
        for items in families:
            superseded = {item.get("supersedes") for item in items} - {None}
            for item in items:
                if item["accepted"] or item["id"] in superseded or item.get("parentRevision") != accepted:
                    continue
                result.append({"workspaceId": workspace, "id": item["id"], "kind": item.get("kind"),
                               "subject": item.get("subject") or "", "createdAt": epoch(item.get("createdAt"))})
    return result


def proposal_findings(proposals, now):
    findings = []
    for item in proposals:
        if item["createdAt"] is None or now - item["createdAt"] <= PROPOSAL_HOURS * 3600:
            continue
        hours = int((now - item["createdAt"]) // 3600)
        label = KINDS.get(item["kind"], "zadání")
        subject = f" „{item['subject']}“" if item["subject"] else ""
        findings.append({"key": f"truth:proposal-stale:{item['workspaceId']}:{item['id']}",
                         "rule": "truth.proposal-stale", "severity": "warn", "workspaceId": item["workspaceId"],
                         "message": f"Návrh ({label}){subject} čeká na rozhodnutí člověka {hours} h.",
                         "data": {"proposalId": item["id"], "kind": label, "waitingHours": hours}})
    return findings


def run(ctx):
    return [*worktree_findings(read_worktrees(ctx.service, ctx.project)),
            *proposal_findings(read_proposals(ctx.service, ctx.project), ctx.now)]


GUARD = Guard(id="pravda", label="Pravda a synchronizace", every_s=300, run=run)
