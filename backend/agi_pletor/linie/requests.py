"""Žádost srdci (docs/navrhy/2026-11-06-linie-rebrand.md §4a, §7 bod 5): `<data>/projects/<p>/linie/requests.json`.

Žádost `{id, text, idempotencyKey, by, at, steps}`; `create` vrátí ihned `steps: [{k: 'accepted', at, by}]` a do deníku
zapíše jen `linie.request.accepted`. Kroky `plan`, `ticket`, `attempt`, `commit` přidává výhradně `confirm` s důkazem,
který se ověří proti skutečnému záznamu (karta v grafu, ticket s `work.requestId`, pokus v `work.attempts`, commit na
větvi úkolu s trailerem `Opora-Mark` jeho značky); bez důkazu 422. Každé potvrzení je vlastní krok `{k, at, by,
evidence}`, takže žádost se může větvit (dva tickety = dva kroky `ticket`); stejný krok se stejným důkazem se
nezdvojí. Selhání `{k, failed: True, why, at, by}` zůstává viditelné. Otevřená = bez kroku `commit`.
Trailer určuje vazbu, nepotvrzuje splnění žádosti.
"""
import re
from pathlib import Path

from backend.agi_pletor.linie import idempotency, journal, jsonfile
from backend.agi_pletor.linie import work as work_mod
from backend.brain_opora.determinism.gate_payloads import GateError
from database.repositories.tickets import TicketStore

STEPS = ("plan", "ticket", "attempt", "commit")
MARK = re.compile(r"^Opora-Mark:\s*(\S+)", re.MULTILINE)
HINT = "Krok přidá jen potvrzení se skutečným důkazem: POST /api/pletor/requests/{id}/steps {k, evidence}."


def _path(data_root, project):
    return Path(data_root) / "projects" / project / "linie" / "requests.json"


def _all(data_root, project):
    found = jsonfile.read(_path(data_root, project), [])
    return [r for r in found if isinstance(r, dict) and r.get("id")] if isinstance(found, list) else []


def is_open(request):
    return not any(step["k"] == "commit" and not step.get("failed") for step in request["steps"])


def listing(service, project, open_only=False):
    return [r for r in _all(service.root, project) if not open_only or is_open(r)]


def get(service, project, request_id):
    found = next((r for r in _all(service.root, project) if r["id"] == request_id), None)
    if found is None:
        raise GateError(404, "request_not_found", "Žádost v projektu neexistuje.", "Seznam vrací GET /api/pletor/requests.")
    return found


def create(service, project, text, key, by, now):
    if not isinstance(text, str) or not text.strip():
        raise GateError(422, "invalid_payload", "text je neprázdné zadání.", "Napište, co má srdce udělat.")
    text = text.strip()

    def act(ident):
        request_id = "rq_" + ident
        known = next((r for r in _all(service.root, project) if r["id"] == request_id), None)
        if known:
            return known
        made = {"id": request_id, "text": text, "idempotencyKey": key, "by": by, "at": now,
                "steps": [{"k": "accepted", "at": now, "by": by}]}
        jsonfile.update(_path(service.root, project), [], lambda found: [*found, made])
        journal.record(service, project, "linie.request.accepted", by, {"request": request_id})
        return made
    return idempotency.once(service, project, "requests", key, {"text": text}, act, now)


def _ticket(service, project, request_id, evidence):
    ticket_id = evidence.get("ticket")
    with service.reading(project):
        ticket = TicketStore(service.db_for(project), project).get(ticket_id) if isinstance(ticket_id, str) else None
    if not ticket or (ticket.get("work") or {}).get("requestId") != request_id:
        raise GateError(422, "evidence_invalid", f"Ticket {ticket_id} nepatří k žádosti {request_id}.", HINT)
    return ticket


def _verify(service, project, request_id, k, evidence):
    """Důkaz kroku ověřený proti záznamu; vrací uložený tvar důkazu."""
    if not isinstance(evidence, dict) or not evidence:
        raise GateError(422, "evidence_required", f"Krok {k} se bez důkazu nepřidá.", HINT)
    if k == "plan":
        card, workspace = evidence.get("cardId"), evidence.get("workspace") or "main"
        try:
            nodes = {n["id"] for n in service.view(project, workspace)["graph"].get("nodes", [])}
        except (KeyError, ValueError, LookupError):
            nodes = set()
        if card not in nodes:
            raise GateError(422, "evidence_invalid", f"Karta {card} v prostoru {workspace} není.", HINT)
        return {"cardId": card, "workspace": workspace}
    ticket = _ticket(service, project, request_id, evidence)
    work = ticket["work"]
    if k == "ticket":
        return {"ticket": ticket["ticketId"]}
    if k == "attempt":
        found = next((a for a in work.get("attempts") or [] if a["attemptId"] == evidence.get("attemptId")), None)
        if not found:
            raise GateError(422, "evidence_invalid", f"Pokus {evidence.get('attemptId')} u ticketu není.", HINT)
        return {"ticket": ticket["ticketId"], "attemptId": found["attemptId"], "branch": found["branch"]}
    full = work_mod.on_branch(work, evidence.get("sha"))  # commit na větvi úkolu nad bází, jinak 409
    message = work_mod.git(work["repository"], "log", "-1", "--format=%B", full, optional=True) or ""
    if work.get("mark") not in MARK.findall(message):
        raise GateError(422, "evidence_invalid", f"Commit {full[:7]} nenese Opora-Mark: {work.get('mark')}.", HINT)
    return {"ticket": ticket["ticketId"], "sha": full}


def confirm(service, project, request_id, k, by, now, evidence=None, failed=False, why=None):
    """Potvrzený krok (nebo viditelné selhání) žádosti; stejný krok se stejným důkazem vrátí žádost beze změny."""
    get(service, project, request_id)
    if k not in STEPS:
        raise GateError(422, "invalid_payload", f"k je jedno z {', '.join(STEPS)}.", HINT)
    if failed:
        if not isinstance(why, str) or not why.strip():
            raise GateError(422, "invalid_payload", "Selhání kroku nese neprázdné why.", HINT)
        step = {"k": k, "failed": True, "why": why.strip(), "at": now, "by": by}
    else:
        step = {"k": k, "at": now, "by": by, "evidence": _verify(service, project, request_id, k, evidence)}
    added = {}

    def change(found):
        out = []
        for request in found:
            if request.get("id") == request_id and not any(
                    s["k"] == k and s.get("evidence") == step.get("evidence") and s.get("why") == step.get("why")
                    for s in request["steps"]):
                request = {**request, "steps": [*request["steps"], step]}
                added["step"] = step
            out.append(request)
        return out
    jsonfile.update(_path(service.root, project), [], change)
    if added:
        evidence = step.get("evidence") or {}
        journal.record(service, project, "linie.request.failed" if failed else "linie.request.step", by,
                       {"request": request_id, "ticket": evidence.get("ticket"), "sha": evidence.get("sha")},
                       k=k, **({"why": step["why"]} if failed else {}))
    return get(service, project, request_id)


def follow(service, project, shown, k, by, now, **evidence):
    """Automatický krok po operaci Linie (pokus, report), když práce patří k žádosti; neověřený důkaz krok nepřidá."""
    request_id = (shown.get("work") or {}).get("requestId")
    if not request_id:
        return None
    try:
        return confirm(service, project, request_id, k, by, now, {"ticket": shown["ticketId"], **evidence})
    except GateError:
        return None  # shortcut: commit bez traileru nebo smazaná žádost krok jen nepřidá; důvod se nikam nehlásí
