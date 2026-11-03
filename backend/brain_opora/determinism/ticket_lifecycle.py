"""Životní cyklus ticketu navázaný na exekuci (docs/navrhy/2026-11-03-novy-zaklad.md §3.3): jediné místo vazby.

Exekuce zůstává vnitřní mechanikou (lease, kroky, výsledky, PR); ticket z ní jen čte fakta a posouvá se po povolených
přechodech `ticket_model.advance`:

- `bind`: `ticket.claim` s `executionId` smí jen na běžící exekuci karty ticketu (`cardId`) ve stejném prostoru,
  kterou nedrží jiný otevřený ticket; jinak 409 `ticket_execution`.
- `follow`: `delivered` → `verified`, když výsledek exekuce nese `selfChecks` a všechny prošly, nebo když je PR
  exekuce sloučený; `verified` → `closed` po sloučení PR (GitHub i lokální sloučení); zrušená exekuce
  (`cancelled`) → `failed`. Bez navázaného ticketu se nestane nic.
- `safe_follow`: háček pro místa exekucí (výsledek, sloučení, zrušení). Chyba ticketu exekuci nikdy nezastaví.

Transakci a zámky vlastní volající; nic tu nevolá model.
"""
import json
import logging

from backend.brain_opora.determinism import tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.ticket_model import TRANSITIONS, advance
from database.repositories.tickets import TicketStore

LOG = logging.getLogger(__name__)
OPEN = ("draft", "issued", "claimed", "in_progress", "needs_answer", "delivered", "verified")
BIND_HINT = "Pošlete executionId běžící exekuce karty ticketu (machine.cardId) ze startu exekuce v tomto prostoru."


def _execution(db, project, execution_id):
    row = db.execute("SELECT workspace_id, node_id, record FROM opora_executions WHERE id=? AND project_id=?",
                     (execution_id, project)).fetchone()
    if row is None:
        return None
    return {"workspace": row[0], "nodeId": row[1], "state": json.loads(row[2]).get("state")}


def bind(db, project, ticket, execution_id):
    """Ověří, že `execution_id` smí ticket nést; jinak 409 `ticket_execution`."""
    found = _execution(db, project, execution_id)
    reason = None
    if found is None:
        reason = "Exekuce v projektu neexistuje."
    elif found["workspace"] != ticket["workspaceId"]:
        reason = "Exekuce patří jinému pracovnímu prostoru."
    elif not ticket["machine"]["cardId"] or found["nodeId"] != ticket["machine"]["cardId"]:
        reason = "Exekuce nepatří ke kartě ticketu."
    elif found["state"] != "running":
        reason = "Exekuce už neběží."
    elif ticket["machine"]["executionId"] not in (None, execution_id):
        reason = "Ticket je navázaný na jinou exekuci."
    else:
        other = TicketStore(db, project).by_execution(execution_id)
        if other and other["ticketId"] != ticket["ticketId"] and other["status"] in OPEN:
            reason = "Exekuci drží jiný otevřený ticket."
    if reason:
        raise GateError(409, "ticket_execution", reason, BIND_HINT)


def _verified(db, project, execution_id):
    """Výsledek exekuce s `selfChecks`, kde všechny kontroly prošly."""
    for (record,) in db.execute("SELECT record FROM opora_execution_results WHERE project_id=? AND execution_id=?",
                                (project, execution_id)).fetchall():
        checks = ((json.loads(record).get("result") or {}).get("selfChecks") or {}).get("checks") or []
        if checks and all(item.get("status") == "passed" for item in checks):
            return True
    return False


def _merged(db, project, execution_id):
    return db.execute("SELECT 1 FROM opora_execution_pull_requests WHERE project_id=? AND execution_id=?"
                      " AND state='merged'", (project, execution_id)).fetchone() is not None


def _next(db, project, ticket):
    execution_id, status = ticket["machine"]["executionId"], ticket["status"]
    found = _execution(db, project, execution_id)
    if found and found["state"] == "cancelled" and "failed" in TRANSITIONS.get(status, ()):
        return "failed"
    if status == "delivered" and (_verified(db, project, execution_id) or _merged(db, project, execution_id)):
        return "verified"
    if status == "verified" and _merged(db, project, execution_id):
        return "closed"
    return None


def follow(db, project, ticket, now=None):
    """Posune ticket podle faktů jeho exekuce (po jednom přechodu přes `advance`); vrátí výsledný stav."""
    if not ticket or not ticket["machine"]["executionId"]:
        return ticket and ticket["status"]
    store, at, status = TicketStore(db, project), tokens.stamp(now), ticket["status"]
    target = _next(db, project, ticket)
    while target is not None:
        if not store.move(ticket["ticketId"], status, advance(status, target), at):
            break  # mezitím změnil stav někdo jiný; jeho zápis platí
        status = target
        target = _next(db, project, {**ticket, "status": status})
    return status


def safe_follow(db, project, execution_id, now=None):
    """Háček exekucí: ticket navázaný na `execution_id` dožene fakta; bez ticketu nic, chyba se jen zaloguje."""
    try:
        return follow(db, project, TicketStore(db, project).by_execution(execution_id), now)
    except Exception:  # ticket je doplněk, exekuce musí doběhnout jako dřív
        LOG.exception("Ticket exekuce %s se nepodařilo posunout.", execution_id)
        return None
