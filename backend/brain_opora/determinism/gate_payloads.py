"""Kontrola těl brány mimo druhy požadavků a její chyby (docs/brain-gate.md §4 „Errors“).

Těla jednotlivých druhů `{kind, body}` kontroluje tabulka `kinds.py`. Každá chyba 4xx nese `code` a `hint`
s dalším krokem, jako od #139.
"""
import json

from backend.canvas.graph import valid_id

MAX_BODY = 64 * 1024
MAX_INBOX_WAIT = 30
NAME_LIMIT = 80
TEXT_LIMIT = 4000
SESSION_EXAMPLE = {"project": "draft", "workspace": "draft", "worker": {"name": "office-dev-1"}}


class GateError(Exception):
    """Odmítnutí brány: HTTP stav, strojový `code` a `hint` s dalším krokem."""

    def __init__(self, status, code, message, hint):
        super().__init__(message)
        self.status, self.code, self.hint = status, code, hint

    def body(self):
        return {"error": str(self), "code": self.code, "hint": self.hint}


def invalid(message, hint):
    return GateError(422, "invalid_payload", message, hint)


def parse_body(raw):
    """Tělo JSON do 64 KB; větší dostane 413, nečitelné 422."""
    if len(raw) > MAX_BODY:
        raise GateError(413, "body_too_large", "Tělo požadavku brány je větší než 64 KB.",
                        "Zkraťte tělo; velké podklady patří do souboru v repozitáři, do brány jen odkaz.")
    try:
        return json.loads(raw or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise invalid("Tělo není platný JSON.", "Pošlete objekt JSON s Content-Type: application/json.") from None


def _short_text(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= NAME_LIMIT


def session_payload(payload):
    """`{project, workspace, worker: {name, office?, floor?}}` → `(project, workspace, worker)`."""
    hint = "Tělo je " + json.dumps(SESSION_EXAMPLE, ensure_ascii=False) + "; worker.office a worker.floor jsou volitelné."
    if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "worker"}:
        raise invalid("Relace brány potřebuje přesně project, workspace a worker.", hint)
    project, workspace, worker = payload["project"], payload["workspace"], payload["worker"]
    if not (project == "draft" or valid_id(project)) or not valid_id(workspace):
        raise invalid("Neplatné ID projektu nebo pracovního prostoru.", hint)
    if not isinstance(worker, dict) or not set(worker) <= {"name", "office", "floor"} or "name" not in worker:
        raise invalid("worker je objekt {name, office?, floor?}.", hint)
    if not all(_short_text(worker[key]) for key in worker):
        raise invalid(f"Pole pracovníka jsou neprázdné texty do {NAME_LIMIT} znaků.", hint)
    return project, workspace, {key: value.strip() for key, value in worker.items()}


def answer_payload(payload):
    """`{answer}` → odpověď (libovolná hodnota JSON kromě null)."""
    if not isinstance(payload, dict) or set(payload) != {"answer"} or payload["answer"] is None:
        raise invalid("Odpověď na lístek je {answer}.", 'Například {"answer": {"text": "Ano, pokračujte."}}.')
    return payload["answer"]


def _inbox_bounds(after, wait, hint):
    if after < 0 or not 0 <= wait <= MAX_INBOX_WAIT:
        raise invalid("after je ≥ 0 a wait v rozsahu 0..30.", hint)
    return after, wait


def inbox_query(after, wait):
    """`?after=<seq>&wait=<0..30>` → `(after, wait)` jako celá čísla."""
    hint = "Například /api/gate/inbox?after=0&wait=20."
    try:
        after, wait = int(after or 0), int(wait or 0)
    except (TypeError, ValueError):
        raise invalid("after a wait jsou celá čísla.", hint) from None
    return _inbox_bounds(after, wait, hint)


def inbox_body(body):
    """Tělo druhu `inbox` `{after?, wait?}` → `(after, wait)`; stejné meze jako `?after&wait`."""
    hint = 'Například {"kind": "inbox", "body": {"after": 0, "wait": 20}}.'
    body = shaped(body, (), ("after", "wait"), hint=hint)
    if any(type(value) is not int for value in body.values()):
        raise invalid("after a wait jsou celá čísla.", hint)
    return _inbox_bounds(body.get("after", 0), body.get("wait", 0), hint)


def _filled(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit and "\0" not in value


def shaped(body, required, optional=(), *, texts=(), ids=(), limit=TEXT_LIMIT, hint):
    """Tělo druhu s přesně danými klíči: `required` povinné, `optional` volitelné; chybějící tělo = `{}`.

    `texts` jsou neprázdné texty do `limit` znaků, `ids` ID (písmena, číslice, _ a -). Vrací tělo beze změny.
    """
    body = {} if body is None else body
    keys = [*required, *(key + "?" for key in optional)]
    if not isinstance(body, dict) or not set(required) <= set(body) <= {*required, *optional}:
        raise invalid("Tělo je přesně {" + ", ".join(keys) + "}.", hint)
    for key, value in body.items():
        if key in ids and not valid_id(value):
            raise invalid(f"{key} je ID (písmena, číslice, _ a -).", hint)
        if key in texts and not _filled(value, limit):
            raise invalid(f"{key} je neprázdný text do {limit} znaků.", hint)
    return body
