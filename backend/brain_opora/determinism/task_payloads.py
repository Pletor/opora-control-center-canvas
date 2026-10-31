"""Kontrola těl fronty úkolů (docs/brain-gate.md §6, H1b): zápis úkolu a hlášení `report`.

Úkol má pevný tvar, který pracovník dostane vždy celý: chybějící volitelná pole se doplní prázdnou hodnotou.
Každé odmítnutí je `GateError` s `code` a `hint`.
Volitelný sprint (docs/navrhy/2026-10-31-sprinty-a-uspornost.md §2) žije v těle: `sprint = {id, goal?, milestone[]?}`;
úkol bez sprintu tělo nemění. Kontrola smí mít stav `deferred` (ověří ji kontrolní bod sprintu, `task_queue.report`).
"""
import json
import re

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id

STATUSES = ("ready", "assigned", "done", "failed", "cancelled")
CHECK_STATUSES = ("green", "red", "deferred")
SHA = re.compile(r"[0-9a-fA-F]{7,40}")
TITLE_LIMIT = 200
TEXT_LIMIT = 4000
MAX_CHECKS = 50
MAX_ORDER = 1_000_000
SPRINT_ID_LIMIT = 40
# model pracovníka: výchozí Sonnet (eval m6: stejná kvalita jako Opus za ~55 % ceny), Opus jen na žádost srdce
MODELS = ("sonnet", "opus", "haiku", "fable")
DEFAULT_MODEL = "sonnet"
TASK_EXAMPLE = {"project": "draft", "workspace": "draft", "title": "Přidat test",
                "body": {"do": "Doplňte test pro modul X.", "doneWhen": ["npm test je zelený"]}}
REPORT_EXAMPLE = {"taskId": "ht_…", "sha": "abc1234", "summary": "Hotovo.",
                  "checks": [{"name": "npm test", "status": "green"}]}
SPRINT_EXAMPLE = {"id": "S1", "goal": "Základ webu stojí.", "milestone": ["npm run build projde"]}
TASK_HINT = ("Tělo je " + json.dumps(TASK_EXAMPLE, ensure_ascii=False)
             + "; nodeId a order (celé číslo, nižší jde dřív) jsou volitelné; body.sprint je volitelně "
             + json.dumps(SPRINT_EXAMPLE, ensure_ascii=False) + " (goal a milestone stačí u jednoho úkolu sprintu).")
REPORT_HINT = ("Tělo hlášení je " + json.dumps(REPORT_EXAMPLE, ensure_ascii=False)
               + "; mimo kontrolní bod sprintu smí kontroly mít stav deferred.")
REASON_LIMIT = 400
RELEASE_HINT = ('Tělo vrácení je {"taskId": "ht_…", "reason": "Úkol potřebuje soubor mimo files."}; '
                f"reason je krátký text do {REASON_LIMIT} znaků.")


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


def _sprint(value):
    """`{id, goal?, milestone[]?}`: id krátký neprázdný text, goal text, milestone seznam textů."""
    return (isinstance(value, dict) and "id" in value and set(value) <= {"id", "goal", "milestone"}
            and _text(value["id"], SPRINT_ID_LIMIT, True) and _text(value.get("goal", ""))
            and _texts(value.get("milestone", [])))


def task_body(body):
    """`{why, do, files[], doneWhen[], dontTouch[{path, heldBy}], context{…}, commit, model, sprint?}` s doplněnými
    poli; `sprint` zůstane jen u úkolu, který ho nese (bez doplnění, ať úkol bez sprintu má tělo jako dřív)."""
    fields = {"why", "do", "files", "doneWhen", "dontTouch", "context", "commit", "model", "sprint"}
    if not isinstance(body, dict) or not set(body) <= fields or not _text(body.get("do"), required=True):
        raise invalid("Tělo úkolu je objekt s povinným do a poli why, files, doneWhen, dontTouch, context, commit, model,"
                      " sprint.", TASK_HINT)
    if "sprint" in body and not _sprint(body["sprint"]):
        raise invalid(f"sprint je {{id, goal?, milestone[]?}}: id neprázdný text do {SPRINT_ID_LIMIT} znaků, goal text,"
                      " milestone seznam textů.", TASK_HINT)
    full = {"why": "", "files": [], "doneWhen": [], "dontTouch": [], "context": {}, "commit": "", "model": DEFAULT_MODEL, **body}
    if not (_text(full["why"]) and _texts(full["files"]) and _texts(full["doneWhen"]) and _held(full["dontTouch"])
            and _context(full["context"]) and _text(full["commit"], 400) and full["model"] in MODELS):
        raise invalid("Pole úkolu mají špatný tvar: texty, seznamy textů, dontTouch = [{path, heldBy}], model = "
                      + " | ".join(MODELS) + ".", TASK_HINT)
    if "sprint" in full:  # stejný sprint = stejné id; okrajové mezery by sprint rozdělily
        full["sprint"] = {**full["sprint"], "id": full["sprint"]["id"].strip()}
    # eval m3/m6: soubor ve files i v dontTouch zastavil pracovníka lístkem; rozpor odmítne už zápis úkolu
    clash = sorted(set(full["files"]) & {item["path"] for item in full["dontTouch"]})
    if clash:
        raise GateError(422, "files_held", "Soubor je zároveň ve files i v dontTouch: " + ", ".join(clash) + ".",
                        "Úkol, který soubor mění, ho nesmí mít v dontTouch. Seřaď úkoly přes order, "
                        "nebo změnu přesuň do nového souboru a v drženém nech jen import.")
    return full


def task_fields(payload):
    """`{nodeId?, order?, title, body}` → `(nodeId, title, body, order)`; projekt a prostor dodá volající."""
    if not isinstance(payload, dict) or not {"title", "body"} <= set(payload)             or not set(payload) <= {"nodeId", "order", "title", "body"}:
        raise invalid("Úkol potřebuje title a body (nodeId a order jsou volitelné).", TASK_HINT)
    order, node = payload.get("order", 0), payload.get("nodeId")
    if type(order) is not int or not 0 <= order <= MAX_ORDER:
        raise invalid(f"order je celé číslo 0 až {MAX_ORDER}; nižší jde dřív, při shodě rozhoduje pořadí vzniku.",
                      TASK_HINT)
    if node is not None and not valid_id(node):
        raise invalid("nodeId je ID karty (písmena, číslice, _ a -).", TASK_HINT)
    if not _text(payload["title"], TITLE_LIMIT, True):
        raise invalid(f"title je neprázdný text do {TITLE_LIMIT} znaků.", TASK_HINT)
    return node, payload["title"].strip(), task_body(payload["body"]), order


def task_payload(payload):
    """`{project, workspace, nodeId?, order?, title, body}` → `(project, workspace, nodeId, title, body, order)`."""
    if not isinstance(payload, dict) or not {"project", "workspace"} <= set(payload):
        raise invalid("Úkol potřebuje project, workspace, title a body (nodeId a order jsou volitelné).", TASK_HINT)
    project, workspace = payload["project"], payload["workspace"]
    if not (project == "draft" or valid_id(project)) or not valid_id(workspace):
        raise invalid("Neplatné ID projektu nebo pracovního prostoru.", TASK_HINT)
    rest = {key: value for key, value in payload.items() if key not in ("project", "workspace")}
    return project, workspace, *task_fields(rest)


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
        raise invalid(f"Každá kontrola je {{name, status: green | red | deferred, output?}}, nejvýš {MAX_CHECKS}.",
                      REPORT_HINT)
    return body["taskId"], body["sha"].lower(), body["summary"], checks


def release_payload(body):
    """`{taskId, reason}` druhu `release` → `(taskId, reason)`; důvod je povinný krátký text."""
    if not isinstance(body, dict) or set(body) != {"taskId", "reason"}:
        raise invalid("Vrácení úkolu je přesně {taskId, reason}.", RELEASE_HINT)
    if not valid_id(body["taskId"]) or not _text(body["reason"], REASON_LIMIT, True):
        raise invalid(f"taskId je ID úkolu z odpovědi next a reason neprázdný text do {REASON_LIMIT} znaků.",
                      RELEASE_HINT)
    return body["taskId"], body["reason"].strip()
