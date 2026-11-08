"""Otázky Pletora srdci (docs/navrhy/2026-11-08-pletor-otazky-srdci.md): `<data>/projects/<p>/brain/pletor_questions.json`.

Otázka `{id: pq_…, workspace, text, status: asked | answered | closed, askedAt, refinements: [{text, at}],
answers: [{text, refs, unknown, reason?, at, by}], closedAt?, closedNote?}`. Na projekt je nejvýš jedna otevřená
(`status != closed`): `ask` bez ní založí novou, s ní přidá upřesnění a vrátí stav na `asked`. Odpovídá jen srdce
(`answer`, kontrolu původce dělá routa), uzavírá člověk přes Pletora (`close`). Zápis pod zámkem `linie/jsonfile`.
"""
import uuid

from backend.agi_pletor.linie import jsonfile
from backend.brain_opora.determinism import brain_files
from backend.brain_opora.determinism.gate_payloads import GateError, invalid

FILE = "pletor_questions.json"
MAX_REFS = 10
TEXT_LIMIT = 8000  # stejný strop jako akce Pletora a zpráva srdci
HINT = 'Příklad: {"text": "…", "refs": ["vf_…"], "unknown": false}'


def _path(service, project):
    return brain_files.brain_dir(service, project) / FILE


def listing(service, project):
    found = jsonfile.read(_path(service, project), [])
    return [q for q in found if isinstance(q, dict) and q.get("id")] if isinstance(found, list) else []


def current(items):
    """Otevřená otázka projektu, nebo None."""
    return next((q for q in reversed(items) if q.get("status") != "closed"), None)


def ask(service, project, workspace, text, at):
    """`(otázka, upřesnění?)`: bez otevřené otázky založí novou, jinak k ní přidá upřesnění a vrátí ji do fronty."""
    # OP-FB0522.1: jedna otevřená otázka na projekt; další dotaz Pletora je upřesnění téže, ne nová fronta
    made = {}

    def change(items):
        items = [q for q in items if isinstance(q, dict) and q.get("id")] if isinstance(items, list) else []
        found = current(items)
        if found:
            found["refinements"].append({"text": text, "at": at})
            found["status"] = "asked"
            made.update(question=found, refined=True)
        else:
            found = {"id": "pq_" + uuid.uuid4().hex[:12], "workspace": workspace, "text": text, "status": "asked",
                     "askedAt": at, "refinements": [], "answers": []}
            items.append(found)
            made.update(question=found, refined=False)
        return items

    jsonfile.update(_path(service, project), [], change)
    return made["question"], made["refined"]


def _checked(text, refs, unknown, reason):
    text = text.strip() if isinstance(text, str) else ""
    if not text or len(text) > TEXT_LIMIT or "\0" in text:
        raise invalid(f"text je neprázdný text do {TEXT_LIMIT} znaků.", HINT)
    if not isinstance(refs, list) or len(refs) > MAX_REFS or not all(isinstance(r, str) and r.strip() for r in refs):
        raise invalid(f"refs je nejvýš {MAX_REFS} neprázdných řetězců.", HINT)
    reason = reason.strip() if isinstance(reason, str) else ""
    if unknown and not reason:
        raise invalid("Odpověď unknown potřebuje reason: proč nevíme a co by to rozhodlo.",
                      'Příklad: {"text": "Nevím.", "unknown": true, "reason": "Chybí přístup k …"}')
    entry = {"text": text, "refs": [r.strip() for r in refs], "unknown": bool(unknown)}
    return entry | ({"reason": reason} if unknown else {})


def answer(service, project, question_id, text, refs, unknown, reason, by, at):
    """`(otázka, změněno?)`; neznámá 404, uzavřená 409, vadná odpověď 422. Stejná odpověď jako poslední = beze změny."""
    entry = _checked(text, refs, unknown, reason)
    made = {}

    def change(items):
        items = [q for q in items if isinstance(q, dict) and q.get("id")] if isinstance(items, list) else []
        found = next((q for q in items if q["id"] == question_id), None)
        if found is None:
            raise GateError(404, "question_not_found", "Otázka Pletora neexistuje.", "ID najdete v GET /api/pletor/questions.")
        if found.get("status") == "closed":
            raise GateError(409, "question_closed", "Otázku už člověk uzavřel.", "Na uzavřenou otázku se neodpovídá.")
        last = (found.get("answers") or [{}])[-1]
        keys = ("text", "refs", "unknown", "reason")
        # Opakované volání nástroje srdce se stejnou odpovědí nezdvojí záznam ani nespustí nový výklad.
        if found["status"] == "answered" and all(last.get(key) == entry.get(key) for key in keys):
            made.update(question=found, changed=False)
            return items
        found.setdefault("answers", []).append({**entry, "at": at, "by": by})
        found["status"] = "answered"
        made.update(question=found, changed=True)
        return items

    jsonfile.update(_path(service, project), [], change)
    return made["question"], made["changed"]


def close(service, project, note, at):
    """Uzavře otevřenou otázku s poznámkou člověka; bez otevřené otázky None."""
    made = {}

    def change(items):
        items = [q for q in items if isinstance(q, dict) and q.get("id")] if isinstance(items, list) else []
        found = current(items)
        if found:
            found.update(status="closed", closedAt=at, closedNote=note)
        made["question"] = found
        return items

    jsonfile.update(_path(service, project), [], change)
    return made["question"]
