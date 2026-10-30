"""Povolení a strop Jevu vstupní brány (docs/navrhy/2026-10-30-vstupni-brana.md §7).

`settings.brain.intake = {jev, jevPerDay}` v `project.json`, vedle přepínače brány (`gate_setting.py`), čte se a
zapisuje stejně. Volání Jevu posílá větu člověka mimo stroj, proto chybějící nebo poškozená hodnota znamená
vypnuto (`jev: false`) a výchozí strop 200 volání za UTC den. Zapíná a mění ho jen člověk (`require_human` v routě);
tady se jen ověří tělo a projekt. Zápis zachová přepínač brány a ten zase tohle nastavení.
"""
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id

PER_DAY, MAX_PER_DAY = 200, 10_000
DEFAULT = {"jev": False, "jevPerDay": PER_DAY}
EXAMPLE = {"project": "draft", "jev": True, "jevPerDay": PER_DAY}


def _count(value):
    return type(value) is int and 0 <= value <= MAX_PER_DAY


def read(service, pid):
    """`{jev, jevPerDay}`; neznámý projekt, chybějící složka i poškozený soubor = výchozí (vypnuto, 200)."""
    try:
        folder = service.folder(pid)
        brain = folder.read().get("settings", {}).get("brain") if folder.exists() else None
    except (ValueError, OSError, AttributeError):
        brain = None
    stored = brain.get("intake") if isinstance(brain, dict) else None
    if not isinstance(stored, dict):
        return dict(DEFAULT)
    return {"jev": stored.get("jev") is True,
            "jevPerDay": stored["jevPerDay"] if _count(stored.get("jevPerDay")) else PER_DAY}


def _project(service, pid):
    if not isinstance(pid, str) or (pid != "draft" and not valid_id(pid)):
        raise invalid("Neplatný identifikátor projektu.", f"Příklad: {EXAMPLE}.")
    if not service.project_exists(pid):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "Zkontrolujte ID projektu v ?project=.")
    return pid


def get(service, pid):
    """`GET /api/brain/intake-setting?project=`: `{project, jev, jevPerDay}`, čte ho kdokoli."""
    return {"project": _project(service, pid), **read(service, pid)}


def write(service, payload):
    """Zapne nebo vypne Jev vstupní brány a nastaví strop; volá jen routa za `require_human`.
    Tělo `{project, jev, jevPerDay?}`; chybějící `jevPerDay` nechá uložený strop."""
    keys = set(payload) if isinstance(payload, dict) else set()
    if not {"project", "jev"} <= keys <= {"project", "jev", "jevPerDay"} or type(payload["jev"]) is not bool:
        raise invalid("Tělo je {project, jev: true | false, jevPerDay?: 0–10000}.", f"Příklad: {EXAMPLE}.")
    if "jevPerDay" in payload and not _count(payload["jevPerDay"]):
        raise invalid(f"jevPerDay je celé číslo 0–{MAX_PER_DAY}.", f"Příklad: {EXAMPLE}.")
    pid = _project(service, payload["project"])
    with service.lock_for(pid):
        folder = service.folder(pid)
        if not folder.exists():
            raise GateError(409, "project_folder_missing", "Projekt nemá složku s project.json; nastavení nelze uložit.",
                            "Otevřete projekt v UI OPORY, aby se jeho složka založila, a zkuste to znovu.")
        brain = folder.read().get("settings", {}).get("brain")
        brain = brain if isinstance(brain, dict) else {}
        value = {"jev": payload["jev"], "jevPerDay": payload.get("jevPerDay", read(service, pid)["jevPerDay"])}
        folder.update(settings={"brain": {**brain, "intake": value}})
    return get(service, pid)
