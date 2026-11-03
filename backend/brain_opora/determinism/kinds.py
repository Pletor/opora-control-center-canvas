"""Tabulka druhů brány (docs/brain-control-api.md §1, §2, krok H1c): jediné místo, kde druh žije.

Každý druh má roli (`worker` / `heart`), popis, schéma vstupu a výstupu, úplný příklad, chybové kódy s `hint`,
příznak `sync`, kontrolu těla a obsluhu. `GET /api/gate/kinds` je výpis této tabulky pro roli volajícího,
`POST /api/gate/requests` jde přes `run`. Synchronní druh odpoví hned a lístek zůstane jako audit (zodpovězený
branou); `ask` a `change` čekají ve frontě na člověka nebo srdce. Nic tu nevolá model.
"""
import json
from collections.abc import Callable
from dataclasses import dataclass

from backend.brain_opora.determinism import (
    gate,
    snapshot,
    ticket,
    ticket_lifecycle,
    ticket_model,
)
from backend.brain_opora.determinism.gate_payloads import GateError, inbox_body, invalid, shaped
from backend.brain_opora.determinism.kind_schemas import SCHEMAS

ROLES = {"worker": ("worker",), "heart": ("worker", "heart"), "human": ("worker", "heart")}
ESCALATE_LIMIT = 8000
COMMON = {
    "gate_token_invalid": "Založte relaci: POST /api/gate/sessions a pošlete token v hlavičce X-Opora-Gate-Token.",
    "gate_scope": "Token platí jen pro svůj projekt a pracovní prostor; pro jiný založte novou relaci.",
    "invalid_payload": "Pošlete tělo podle schématu input; úplný příklad je v example.",
    "body_too_large": "Zkraťte tělo pod 64 KB; velké podklady patří do souboru v repozitáři, do brány jen odkaz.",
}
HEART_ONLY = {"heart_required": "Tento druh posílá jen srdce projektu; své druhy najdete v GET /api/gate/kinds."}
TICKET_MISSING = {"ticket_not_found": "ID lístku najdete v události gate.ticket nebo ve snímku srdce."}
WORK_MISSING = {"ticket_not_found": ticket.MISSING_HINT}
WORK_STATE = {"ticket_state": "Přechod stavu ticketu není povolený; hint chyby vypíše povolené cíle."}
WORK_HELD = {**WORK_MISSING, **WORK_STATE, "ticket_not_held": ticket.HELD_HINT}


@dataclass(frozen=True)
class Kind:
    """Jeden druh požadavku brány; `handle` je None u druhů, které čekají na odpověď (`sync = False`)."""

    name: str
    role: str
    description: str
    codes: dict
    check: Callable
    handle: Callable | None

    @property
    def sync(self):
        return self.handle is not None

    def public(self):
        """Popis druhu pro `GET /api/gate/kinds`."""
        schema_in, schema_out, example = SCHEMAS[self.name]
        return {"kind": self.name, "role": self.role, "description": self.description, "sync": self.sync,
                "input": schema_in, "output": schema_out, "example": example,
                "codes": [{"code": code, "hint": hint} for code, hint in {**COMMON, **self.codes}.items()]}


def _hint(name):
    return "Příklad: " + json.dumps({"kind": name, "body": SCHEMAS[name][2]}, ensure_ascii=False)


def _empty(body):
    """`state` nemá žádné parametry."""
    if body not in ({}, None):
        raise invalid("Požadavek state má prázdné tělo.", 'Pošlete {"kind": "state"} nebo {"kind": "state", "body": {}}.')


def _ask(body):
    shaped(body, ("question",), texts=("question",), hint=_hint("ask"))


def _change(body):
    shaped(body, ("proposal", "reason"), texts=("proposal", "reason"), hint=_hint("change"))


def _ticket_answer(body):
    shaped(body, ("ticketId", "text"), ("feedbackId",), ids=("ticketId", "feedbackId"), texts=("text",),
           hint=_hint("ticket.answer"))


def _answer(service, session, body, now):
    """Bez `feedbackId` odpověď na čekající lístek (otázka v `gate_tickets`), s ním odpověď na zpětnou vazbu ticketu."""
    if "feedbackId" in body:
        return ticket.answer(service, session, body, now)
    return {"ticket": gate.answer(service, session["project_id"], body["ticketId"], {"answer": {"text": body["text"]}},
                                  "heart", now)}


# Obsluha je `handle(service, session, body, now) -> odpověď`; tělo už prošlo kontrolou `check`.
TABLE = (
    Kind("ask", "worker", "Otázka pro srdce nebo člověka. Lístek čeká ve frontě, odpověď přijde do schránky (inbox).",
         {}, _ask, None),
    Kind("change", "worker", "Návrh změny plánu nebo úkolu pro srdce. Lístek čeká ve frontě, odpověď přijde do "
         "schránky (inbox).", {}, _change, None),
    Kind("state", "worker", "Kompaktní deterministický stav: projekt, záměr, pravidla, plán, počty ticketů podle "
         "stavu a ticket držený touto relací.", {"project_not_found": "ID projektu najdete v GET /api/bootstrap."}, _empty,
         lambda service, session, body, now: snapshot.state(service, session["project_id"], session["workspace_id"],
                                                            session["id"])),
    Kind("inbox", "worker", "Zodpovězené lístky této relace s answeredSeq > after; s wait > 0 čeká až wait sekund. "
         "Další volání pošle after = last.", {}, inbox_body,
         lambda service, session, body, now: gate.inbox(service, session, *inbox_body(body))),
    Kind("ticket.request", "worker", "Žádost o práci: ticket, který relace drží, jinak nejstarší vydaný v prostoru "
         "(nebere ho). Nic k práci = ticket null.", {}, lambda body: shaped(body, (), hint=_hint("ticket.request")),
         ticket.request),
    Kind("ticket.claim", "worker", "Vezme vydaný ticket (issued → claimed); pak ho drží jen tato relace. S executionId "
         "ho naváže na běžící exekuci karty ticketu; stav pak posouvá i exekuce (ověřeno, sloučeno, zrušeno).",
         {**WORK_MISSING, **WORK_STATE, "ticket_execution": ticket_lifecycle.BIND_HINT}, ticket_model.claim_payload,
         ticket.claim),
    Kind("ticket.feedback", "worker", "Zpětná vazba k drženému ticketu: bug, idea, improvement nebo question. "
         "Otázka přepne ticket na needs_answer, odpověď srdce je pak v ticket.request.", WORK_HELD,
         ticket_model.feedback_payload, ticket.feedback),
    Kind("ticket.deliver", "worker", "Odevzdání drženého ticketu se shrnutím (a sha) → delivered. S otevřenou "
         "otázkou nejde.", WORK_HELD, ticket_model.deliver_payload, ticket.deliver),
    Kind("ticket.release", "worker", "Vrátí vzatý ticket do fronty (claimed → issued) bez držitele a bez exekuce, "
         "když kancelář nedostala místo ani exekuci. Rozpracovaný ticket vrátit nejde.", WORK_HELD,
         lambda body: ticket_model.ticket_id(body, _hint("ticket.release")), ticket.release),
    Kind("ticket.issue", "heart", "Vydá ticket práce (issued) v prostoru tokenu srdce: tělo pro dělníka bez ID "
         "(essence, build, openPaths, cautions, skills, doneCriteria) a strojová vrstva (cardId, executionId, "
         "cardVersion).", HEART_ONLY, ticket_model.issue_payload, ticket.issue),
    Kind("ticket.cancel", "heart", "Zruší ticket práce, který už nedává smysl (vydaný, vzatý i rozpracovaný → "
         "cancelled); odevzdaný ani uzavřený ne.", {**HEART_ONLY, **WORK_MISSING, **WORK_STATE},
         lambda body: ticket_model.ticket_id(body, _hint("ticket.cancel")), ticket.cancel),
    Kind("ticket.answer", "heart", "Odpověď srdce (text): bez feedbackId na čekající lístek otázky (pracovník ji "
         "dostane do schránky), s feedbackId na položku zpětné vazby ticketu práce.",
         {**HEART_ONLY, **TICKET_MISSING, "ticket_answered": "Lístek už má odpověď; načtěte ho.",
          "feedback_not_found": "ID položek jsou v GET /api/brain/tickets/{id} v poli feedback.",
          "feedback_answered": "Položka už má odpověď; načtěte ticket znovu."}, _ticket_answer, _answer),
    Kind("escalate", "heart", "Otázka srdce pro člověka (konflikt se záměrem): čekající lístek ask ve velínu.",
         HEART_ONLY, lambda body: shaped(body, ("text",), texts=("text",), limit=ESCALATE_LIMIT,
                                         hint=_hint("escalate")),
         lambda service, session, body, now: {"ticket": gate.escalate(service, session, body["text"], now)}),
)
KINDS = {kind.name: kind for kind in TABLE}


def visible(role):
    """Druhy, které role vidí: pracovník své, srdce a člověk všechny (docs/brain-control-api.md §1.3)."""
    return [kind.public() for kind in TABLE if kind.role in ROLES[role]]


def request_payload(payload):
    """`{kind, body?}` → `(kind, body)`; neznámý druh dostane 422 s výčtem povolených."""
    if not isinstance(payload, dict) or "kind" not in payload or not set(payload) <= {"kind", "body"}:
        raise invalid("Požadavek brány je {kind, body}.", 'Například {"kind": "ask", "body": {"question": "…"}}.')
    if payload["kind"] not in KINDS:
        raise invalid("Neznámý druh požadavku brány.", "Povolené druhy: " + ", ".join(KINDS)
                      + ". Schémata a příklady: GET /api/gate/kinds.")
    return payload["kind"], payload.get("body", {})


def run(service, session, payload, now=None):
    """`POST /api/gate/requests` → lístek. Synchronní druh je už zodpovězený, `ask` / `change` čekají (`queued`)."""
    name, body = request_payload(payload)
    kind = KINDS[name]
    if kind.role == "heart" and session["role"] != "heart":
        raise GateError(403, "heart_required", f"Druh {name} posílá jen srdce projektu.", HEART_ONLY["heart_required"])
    kind.check(body)
    if not kind.sync:
        return gate.record(service, session, name, body, now)
    # Obsluha běží dřív než zápis lístku a se svými zámky: odmítnutý požadavek lístek nezaloží a přehled
    # karet stavu (zámek grafu, pak projektu) se nečte pod zámkem projektu.
    result = kind.handle(service, session, body, now)
    return gate.record(service, session, name, body, now, answered=True, answer=result)
