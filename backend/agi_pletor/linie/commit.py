"""Detail commitu pro Linii (docs/navrhy/2026-11-06-linie-detail-commitu.md): od tečky k plánu, kartě a kanceláři.

`detail(service, project, workspace, root, sha, folder)` → `{commit, ticket, pr, preview, sentence}`. Ticket se hledá
podle větve a rozsahu (`work.branch` commit obsahuje, `work.baseSha` ne); bez ticketu je `ticket: None` a věta to
řekne – nic se nevymýšlí. Karta = trailer `Opora-Node` nebo `machine.cardId`; plán = `spec.steps` přijaté specifikace.
"""
import re
from urllib.parse import urlencode

from backend.agi_pletor.linie import previews
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.graph import gh_prs
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_plan_steps import ordered, steps_of
from backend.integrations.gitio import git
from database.repositories.gate_sessions import GateSessionStore
from database.repositories.tickets import TicketStore

TIMEOUT = 15
FORMAT = "--format=%H%x1f%cI%x1f%an%x1f%s%x1f%b"
TRAILER = re.compile(r"^Opora-(Node|Execution):\s*(\S+)", re.MULTILINE)


def _commit(root, sha):
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", sha or ""):
        raise GateError(404, "commit_not_found", "Commit v repozitáři není.", "Zadejte sha z Git grafu.")
    line = git(root, "log", "-1", FORMAT, sha, "--", timeout=TIMEOUT, optional=True)
    if not line:
        raise GateError(404, "commit_not_found", "Commit v repozitáři není.", "Zadejte sha z Git grafu.")
    full, at, author, title, body = (line.split("\x1f", 4) + [""])[:5]  # prázdné tělo: výstup gitu je oříznutý
    trailers = {kind.lower(): value for kind, value in TRAILER.findall(body)}
    stat = (git(root, "show", "--stat", "--format=", full, timeout=TIMEOUT, optional=True) or "").strip()
    files = len((git(root, "show", "--name-only", "--format=", full, timeout=TIMEOUT, optional=True) or "").split())
    branches = (git(root, "branch", "--format=%(refname:short)", "--contains", full, timeout=TIMEOUT, optional=True)
                or "").split()
    return {"sha": full, "sha7": full[:7], "title": title, "body": body.strip(), "at": at, "author": author,
            "files": files, "stat": stat, "branches": branches,
            "trailers": {"node": trailers.get("node"), "execution": trailers.get("execution")}}


def _contains(root, older, newer):
    return git(root, "merge-base", "--is-ancestor", older, newer, timeout=TIMEOUT, optional=True) is not None


def _ticket_for(root, tickets, sha, branches):
    """Nejnovější ticket, jehož větev commit obsahuje a jehož výchozí commit ho neobsahuje."""
    for ticket in reversed(tickets):
        work = ticket["work"]
        if work["branch"] in branches and not _contains(root, sha, work["baseSha"]):
            return ticket
    return None


def _card(service, project, workspace, node_id):
    if not node_id:
        return None
    try:
        nodes = service.view(project, workspace)["graph"]["nodes"]
    except (ValueError, KeyError):  # projekt bez plátna: karta se jen pojmenuje podle ID
        nodes = []
    found = next((n for n in nodes if n["id"] == node_id), None)
    link = "/?" + urlencode({"project": project, "workspace": workspace, "screen": "canvas", "node": node_id,
                             "ohCard": node_id, "ohTab": "steps"})
    return {"id": node_id, "name": (found or {}).get("name") or node_id, "link": link, "known": found is not None}


def _plan(service, project, workspace, node_id):
    if not node_id:
        return []
    try:
        documents = OporaChangesets(service).context(project, workspace)["acceptedDocuments"]
    except (KeyError, ValueError, TypeError):
        return []
    fields = next((item.get("fields") for item in documents if item.get("nodeId") == node_id), None)
    return [{k: step.get(k) for k in ("id", "order", "title", "acceptance", "kind")} for step in ordered(steps_of(fields))]


def _office(service, project, ticket):
    session = GateSessionStore(service.db_for(project)).get(ticket["sessionId"]) if ticket.get("sessionId") else None
    machine = ticket["machine"]
    if session is None and not (machine.get("department") or machine.get("executionId")):
        return None
    return {"worker": (session or {}).get("worker_name"), "role": (session or {}).get("role"),
            "department": machine.get("department"), "profile": machine.get("profile"),
            "executionId": machine.get("executionId")}


def _preview(root, folder, sha, branches):
    for record in previews.status(folder):
        if record.get("state") == "running" and record.get("branch") in branches and record.get("sha") \
                and _contains(root, sha, record["sha"]):
            return {"url": record.get("url"), "state": "running", "sha": record["sha"], "branch": record["branch"]}
    return None


def sentence(commit, ticket, pr):
    where = commit["branches"][0] if commit["branches"] else "mimo větve"
    head = f"Commit {commit['sha7']} na {where}: {commit['title']}."
    if ticket is None:
        tail = "Bez evidovaného plánu (žádný ticket)."
    else:
        card = ticket["card"]["name"] if ticket.get("card") else "bez karty"
        who = (ticket.get("office") or {}).get("worker") or "kancelář neevidována"
        tail = f"Plán: {ticket['body']['essence'].splitlines()[0]} (karta {card}, dělá {who}); stav {ticket['stateLabel']}."
    return head + " " + tail + (f" PR #{pr['number']} {pr['state']}." if pr else "")


def detail(service, project, workspace, root, sha, folder, *, pr_lookup=gh_prs):
    commit = _commit(root, sha)
    with service.reading(project):
        tickets = TicketStore(service.db_for(project), project).list_with_work(workspace)
        found = _ticket_for(root, tickets, commit["sha"], commit["branches"])
        ticket = None
        if found is not None:
            shown = work_mod.view(found)
            node_id = commit["trailers"]["node"] or found["machine"].get("cardId")
            ticket = {"ticketId": found["ticketId"], "state": shown["state"], "stateLabel": shown["stateLabel"],
                      "next": shown["next"], "body": found["body"],
                      "work": {k: found["work"].get(k) for k in ("branch", "headSha", "target", "preview")},
                      "card": _card(service, project, workspace, node_id),
                      "office": _office(service, project, found),
                      "plan": _plan(service, project, workspace, node_id)}
    prs = pr_lookup(root)
    pr = next((prs[name] for name in commit["branches"] if name in prs), None)
    return {"commit": commit, "ticket": ticket, "pr": pr, "preview": _preview(root, folder, commit["sha"], commit["branches"]),
            "sentence": sentence(commit, ticket, pr)}
