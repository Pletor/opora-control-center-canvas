"""Cesta práce podle vodotisku (docs/navrhy/2026-11-06-linie-vodotisk-cesty.md): plán → úkol → relace → kód → commit → PR.

`trace(service, project, workspace, root, mark, folder)` sestaví cestu jedním dotazem z tickets (karta, plán, relace)
a gitu (`trace_git`). Každá hrana nese stav `verified` / `claimed` / `inferred`; co chybí, je v `gaps`, nic se nedomýšlí.
Karta, plán a náhled jdou přes stejné funkce jako detail commitu.
"""
import re

from backend.agi_pletor.linie import commit as commit_mod
from backend.agi_pletor.linie import trace_git
from backend.agi_pletor.linie import work as work_mod
from backend.agi_pletor.linie.graph import gh_prs
from backend.brain_opora.determinism.gate_payloads import GateError
from database.repositories.tickets import TicketStore

MARK = re.compile(r"OP-[0-9A-F]{6}")


def _count(n, one, few, many):
    return f"{n} {one if n == 1 else few if 2 <= n <= 4 else many}"


def _runs(root, runs, head):
    return [{k: run.get(k) for k in ("runId", "sessionId", "agent", "startedAt", "fromSha", "revision")}
            | {"status": "verified" if run.get("fromSha") and head and work_mod.ancestor(root, run["fromSha"], head)
               else "claimed"} for run in runs]


def _run_of(root, runs, sha):
    """Nejpozdější relace, která začala nad rodičem commitu (nebo dál před ním), ne jím samým."""
    fits = [r for r in runs if r.get("fromSha") and r["fromSha"] != sha and work_mod.ancestor(root, r["fromSha"], sha)]
    return max(fits, key=lambda r: r["startedAt"])["runId"] if fits else None


def _gaps(commits, places, card):
    gaps = [{"kind": "commit_without_run", "ref": c["sha7"], "text": f"Commit {c['sha7']} bez evidovaného běhu."}
            for c in commits if c["status"] != "claimed" and not c["runId"]]
    gaps += [{"kind": "mark_on_foreign_branch", "ref": c["sha7"],
              "text": f"Commit {c['sha7']} nese značku, ale neleží na větvi úkolu."} for c in commits if c["status"] == "claimed"]
    gaps += [{"kind": "code_without_commit", "ref": f"{p['path']}:{p['line']}",
              "text": f"Značka v {p['path']} bez verified commitu úkolu, který soubor změnil."}
             for p in places if p["status"] == "claimed"]
    return gaps + ([] if card else [{"kind": "no_card", "ref": "", "text": "Úkol nemá kartu zadání."}])


def trace(service, project, workspace, root, mark, folder, *, pr_lookup=gh_prs):
    missing = GateError(404, "mark_not_found", f"Značka {mark} v projektu neexistuje.", "Značku vrací GET /board (mark).")
    if not MARK.fullmatch(mark or ""):
        raise missing
    with service.reading(project):
        tickets = TicketStore(service.db_for(project), project).list_with_work(workspace)
        found = next((t for t in tickets if t["work"].get("mark") == mark), None)
        if found is None:
            raise missing
        work, shown = found["work"], work_mod.view(found)
        commits = trace_git.commits(root, mark, work)
        runs = work.get("runs") or []
        for c in commits:
            c["runId"] = _run_of(root, runs, c["sha"])
        verified = {p for c in commits for p in c["paths"]}
        places = trace_git.code(root, mark, work.get("headSha"), verified)
        nodes = [c["trailers"]["node"] for c in commits if c["status"] != "claimed" and c["trailers"]["node"]]
        node_id = nodes[-1] if nodes else found["machine"].get("cardId")
        card = commit_mod.card(service, project, workspace, node_id)
        plan = commit_mod.plan(service, project, workspace, node_id)
    prs = pr_lookup(root) or {}
    pr = prs.get(work["branch"])
    head = work.get("headSha")
    preview = commit_mod.preview_for(root, folder, head, [work["branch"]]) if head else None
    commits = [{k: c[k] for k in ("sha", "sha7", "title", "at", "author", "branches", "trailers", "runId", "status")}
               for c in commits]
    essence = found["body"]["essence"].splitlines()[0]
    sentence = (f"{mark}: {essence} (karta {card['name'] if card else 'bez karty'}, "
                f"{_count(len(runs), 'relace', 'relace', 'relací')}, {_count(len(commits), 'commit', 'commity', 'commitů')}, "
                f"{_count(len(places), 'místo', 'místa', 'míst')} v kódu"
                + (f", PR #{pr['number']} {pr['state']}" if pr else "") + f"); stav {shown['stateLabel']}.")
    return {"mark": mark,
            "ticket": {"ticketId": found["ticketId"], "title": work.get("title") or essence, "state": shown["state"],
                       "stateLabel": shown["stateLabel"], "next": shown["next"], "body": found["body"],
                       "work": {k: work.get(k) for k in ("branch", "baseSha", "headSha", "target")}},
            "card": card, "revision": found["machine"].get("cardVersion"), "plan": plan,
            "runs": _runs(root, runs, head), "commits": commits, "code": places, "pr": pr,
            "checks": work.get("checks", []), "acceptance": work.get("acceptance"), "merged": work.get("merged"),
            "preview": preview, "gaps": _gaps(commits, places, card), "sentence": sentence}
