"""Tabulka druhů brány (docs/brain-control-api.md §1, §2, krok H1c): jediné místo, kde druh žije.

Každý druh má roli (`worker` / `heart`), popis, schéma vstupu a výstupu, úplný příklad, chybové kódy s `hint`,
příznak `sync`, kontrolu těla a obsluhu. `GET /api/gate/kinds` je výpis této tabulky pro roli volajícího,
`POST /api/gate/requests` jde přes `run`. Synchronní druh odpoví hned a lístek zůstane jako audit (zodpovězený
branou); `ask` a `change` čekají ve frontě na člověka nebo srdce. Nic tu nevolá model.
"""
import json
from collections.abc import Callable
from dataclasses import dataclass

from backend.brain_opora.determinism import gate, snapshot, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError, inbox_body, invalid, shaped
from backend.brain_opora.determinism.kind_schemas import SCHEMAS
from backend.brain_opora.determinism.task_payloads import empty_body, report_payload, task_fields

ROLES = {"worker": ("worker",), "heart": ("worker", "heart"), "human": ("worker", "heart")}
ESCALATE_LIMIT = 8000
COMMON = {
    "gate_token_invalid": "Založte relaci: POST /api/gate/sessions a pošlete token v hlavičce X-Opora-Gate-Token.",
    "gate_scope": "Token platí jen pro svůj projekt a pracovní prostor; pro jiný založte novou relaci.",
    "invalid_payload": "Pošlete tělo podle schématu input; úplný příklad je v example.",
    "body_too_large": "Zkraťte tělo pod 64 KB; velké podklady patří do souboru v repozitáři, do brány jen odkaz.",
}
HEART_ONLY = {"heart_required": "Tento druh posílá jen srdce projektu; své druhy najdete v GET /api/gate/kinds."}
TASK_MISSING = {"task_not_found": "ID úkolu vrací next, task.create nebo GET /api/brain/tasks."}
TICKET_MISSING = {"ticket_not_found": "ID lístku najdete v události gate.ticket nebo ve snímku srdce."}


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


def _ask(body):
    shaped(body, ("question",), ("taskId",), texts=("question",), ids=("taskId",), hint=_hint("ask"))


def _change(body):
    shaped(body, ("proposal", "reason"), ("taskId",), texts=("proposal", "reason"), ids=("taskId",),
           hint=_hint("change"))


def _task_create(body):
    if isinstance(body, dict) and {"project", "workspace"} & set(body):
        raise invalid("Projekt a pracovní prostor bere task.create z tokenu srdce.", _hint("task.create"))
    task_fields(body)


def _scope(session):
    return {"project": session["project_id"], "workspace": session["workspace_id"]}


# Obsluha je `handle(service, session, body, now) -> odpověď`; tělo už prošlo kontrolou `check`.
TABLE = (
    Kind("next", "worker", "Další úkol z fronty: držený úkol znovu, jinak nejstarší ready. Prázdná fronta vrátí "
         "task null a plan (otevřené karty).", {}, empty_body, task_queue.next_task),
    Kind("ask", "worker", "Otázka pro srdce nebo člověka. Lístek čeká ve frontě, odpověď přijde do schránky (inbox).",
         {}, _ask, None),
    Kind("report", "worker", "Hlášení úkolu s kontrolami na sha: vše zelené = done, červená = zpět do ready, "
         "druhá červená = failed.",
         {"invalid_sha": "Pošlete výstup git rev-parse HEAD (nebo jeho zkrácenou podobu).",
          "checks_required": 'Spusťte kontroly a pošlete checks: [{"name": "npm test", "status": "green"}].',
          **TASK_MISSING,
          "task_not_assigned": "Hlaste jen úkol, který vám vrátil next; o další požádejte přes next."},
         report_payload, task_queue.report),
    Kind("change", "worker", "Návrh změny plánu nebo úkolu pro srdce. Lístek čeká ve frontě, odpověď přijde do "
         "schránky (inbox).", {}, _change, None),
    Kind("state", "worker", "Kompaktní deterministický stav: projekt, záměr, pravidla, plán, počty fronty a úkol "
         "držený touto relací.", {"project_not_found": "ID projektu najdete v GET /api/bootstrap."}, empty_body,
         lambda service, session, body, now: snapshot.state(service, session["project_id"], session["workspace_id"],
                                                            session["id"])),
    Kind("inbox", "worker", "Zodpovězené lístky této relace s answeredSeq > after; s wait > 0 čeká až wait sekund. "
         "Další volání pošle after = last.", {}, inbox_body,
         lambda service, session, body, now: gate.inbox(service, session, *inbox_body(body))),
    Kind("task.create", "heart", "Nový úkol ve frontě (ready) v projektu a prostoru tokenu srdce; nižší order jde "
         "dřív.", {**HEART_ONLY, "project_not_found": "ID projektu najdete v GET /api/bootstrap."}, _task_create,
         lambda service, session, body, now: {"task": task_queue.create(service, {**body, **_scope(session)},
                                                                         "heart", now)}),
    Kind("task.cancel", "heart", "Zruší úkol ve stavu ready nebo assigned.",
         {**HEART_ONLY, **TASK_MISSING, "task_closed": "Zrušit jde jen úkol ve stavu ready nebo assigned."},
         lambda body: shaped(body, ("taskId",), ids=("taskId",), hint=_hint("task.cancel")),
         lambda service, session, body, now: {"task": task_queue.cancel(service, session["project_id"],
                                                                         body["taskId"], now, by="heart")}),
    Kind("ticket.answer", "heart", "Odpověď srdce na čekající lístek (answer = {text}); pracovník ji dostane do "
         "schránky.", {**HEART_ONLY, **TICKET_MISSING, "ticket_answered": "Lístek už má odpověď; načtěte ho."},
         lambda body: shaped(body, ("ticketId", "text"), ids=("ticketId",), texts=("text",),
                             hint=_hint("ticket.answer")),
         lambda service, session, body, now: {"ticket": gate.answer(service, session["project_id"], body["ticketId"],
                                                                     {"answer": {"text": body["text"]}}, "heart",
                                                                     now)}),
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
    # karet pro prázdnou frontu (zámek grafu, pak projektu) se nečte pod zámkem projektu.
    result = kind.handle(service, session, body, now)
    return gate.record(service, session, name, body, now, answered=True, answer=result)
