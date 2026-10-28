"""Kontrola těl fronty úkolů (docs/brain-gate.md §6, H1b): zápis úkolu a hlášení `report`.

Úkol má pevný tvar, který pracovník dostane vždy celý: chybějící volitelná pole se doplní prázdnou hodnotou.
Každé odmítnutí je `GateError` s `code` a `hint`.
"""
import json
import re

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id

STATUSES = ("ready", "assigned", "done", "failed", "cancelled")
CHECK_STATUSES = ("green", "red")
SHA = re.compile(r"[0-9a-fA-F]{7,40}")
TITLE_LIMIT = 200
TEXT_LIMIT = 4000
MAX_CHECKS = 50
MAX_ORDER = 1_000_000
TASK_EXAMPLE = {"project": "draft", "workspace": "draft", "title": "Přidat test",
                "body": {"do": "Doplňte test pro modul X.", "doneWhen": ["npm test je zelený"]}}
REPORT_EXAMPLE = {"taskId": "ht_…", "sha": "abc1234", "summary": "Hotovo.",
                  "checks": [{"name": "npm test", "status": "green"}]}
TASK_HINT = ("Tělo je " + json.dumps(TASK_EXAMPLE, ensure_ascii=False)
             + "; nodeId a order (celé číslo, nižší jde dřív) jsou volitelné.")
REPORT_HINT = "Tělo hlášení je " + json.dumps(REPORT_EXAMPLE, ensure_ascii=False) + "."


def _text(value, limit=TEXT_LIMIT, required=False):
    if not isinstance(value, str) or len(value) > limit or "\0" in value:
        return False
    return bool(value.strip()) or not required


def _texts(value):
    return isinstance(value, list) and len(value) <= 100 and all(_text(item, 400, True) for item in value)


def _held(value):
    return (isinstance(value, list) and len(value) <= 100
            and all(isinstance(item, dict) and set(item) == {"path", "heldBy"}
                    and _text(item["path"], 400, True) and _text(item["heldBy"], 200, True) for item in value))


def _context(value):
    if not isinstance(value, dict) or not set(value) <= {"intent", "rules", "pattern"}:
        return False
    return (_text(value.get("intent", "")) and _texts(value.get("rules", []))
            and _text(value.get("pattern", "")))


def task_body(body):
    """`{why, do, files[], doneWhen[], dontTouch[{path, heldBy}], context{…}, commit}` s doplněnými prázdnými poli."""
    fields = {"why", "do", "files", "doneWhen", "dontTouch", "context", "commit"}
    if not isinstance(body, dict) or not set(body) <= fields or not _text(body.get("do"), required=True):
        raise invalid("Tělo úkolu je objekt s povinným do a poli why, files, doneWhen, dontTouch, context, commit.",
                      TASK_HINT)
    full = {"why": "", "files": [], "doneWhen": [], "dontTouch": [], "context": {}, "commit": "", **body}
    if not (_text(full["why"]) and _texts(full["files"]) and _texts(full["doneWhen"]) and _held(full["dontTouch"])
            and _context(full["context"]) and _text(full["commit"], 400)):
        raise invalid("Pole úkolu mají špatný tvar: texty, seznamy textů, dontTouch = [{path, heldBy}].", TASK_HINT)
    return full


def task_payload(payload):
    """`{project, workspace, nodeId?, order?, title, body}` → `(project, workspace, nodeId, title, body, order)`."""
    if not isinstance(payload, dict) or not {"project", "workspace", "title", "body"} <= set(payload) \
            or not set(payload) <= {"project", "workspace", "nodeId", "order", "title", "body"}:
        raise invalid("Úkol potřebuje project, workspace, title a body (nodeId a order jsou volitelné).", TASK_HINT)
    order = payload.get("order", 0)
    if type(order) is not int or not 0 <= order <= MAX_ORDER:
        raise invalid(f"order je celé číslo 0 až {MAX_ORDER}; nižší jde dřív, při shodě rozhoduje pořadí vzniku.",
                      TASK_HINT)
    project, workspace, node = payload["project"], payload["workspace"], payload.get("nodeId")
    if not (project == "draft" or valid_id(project)) or not valid_id(workspace):
        raise invalid("Neplatné ID projektu nebo pracovního prostoru.", TASK_HINT)
    if node is not None and not valid_id(node):
        raise invalid("nodeId je ID karty (písmena, číslice, _ a -).", TASK_HINT)
    if not _text(payload["title"], TITLE_LIMIT, True):
        raise invalid(f"title je neprázdný text do {TITLE_LIMIT} znaků.", TASK_HINT)
    return project, workspace, node, payload["title"].strip(), task_body(payload["body"]), order


def status_filter(status):
    """`?status=` seznamu úkolů: prázdný = všechny, jinak jeden ze stavů."""
    if status and status not in STATUSES:
        raise invalid("Neznámý stav úkolu.", "Povolené stavy: " + ", ".join(STATUSES) + ".")
    return status or None


def empty_body(body):
    """`next` nemá žádné parametry."""
    if body not in ({}, None):
        raise invalid("Požadavek next má prázdné tělo.", 'Pošlete {"kind": "next"} nebo {"kind": "next", "body": {}}.')


def _check(item):
    return (isinstance(item, dict) and {"name", "status"} <= set(item) <= {"name", "status", "output"}
            and _text(item["name"], 200, True) and item["status"] in CHECK_STATUSES
            and _text(item.get("output", ""), TEXT_LIMIT))


def report_payload(body):
    """`{taskId, sha, summary, checks}` → `(taskId, sha malými písmeny, summary, checks)`."""
    if not isinstance(body, dict) or set(body) != {"taskId", "sha", "summary", "checks"}:
        raise invalid("Hlášení je přesně {taskId, sha, summary, checks}.", REPORT_HINT)
    if not valid_id(body["taskId"]) or not _text(body["summary"]):
        raise invalid("taskId je ID úkolu z odpovědi next a summary text do 4000 znaků.", REPORT_HINT)
    if not isinstance(body["sha"], str) or not SHA.fullmatch(body["sha"]):
        raise GateError(422, "invalid_sha", "sha musí mít 7 až 40 hexadecimálních znaků.",
                        "Pošlete výstup git rev-parse HEAD (nebo jeho zkrácenou podobu).")
    checks = body["checks"]
    if not isinstance(checks, list) or not checks:
        raise GateError(422, "checks_required", "Hlášení bez kontrol nejde přijmout.",
                        'Spusťte kontroly a pošlete checks: [{"name": "npm test", "status": "green"}].')
    if len(checks) > MAX_CHECKS or not all(_check(item) for item in checks):
        raise invalid(f"Každá kontrola je {{name, status: green | red, output?}}, nejvýš {MAX_CHECKS}.", REPORT_HINT)
    return body["taskId"], body["sha"].lower(), body["summary"], checks
