"""Výslech srdce zapnutý a strop rešerše na požadavek (docs/navrhy/2026-10-30-vyslech-srdce.md §8).

`settings.brain.brief = {enabled, researchUsd}` v `project.json`, vedle přepínače brány a Jevu vstupní brány
(`intake_setting.py`), čte se a zapisuje stejně. Chybějící nebo poškozená hodnota = výchozí: výslech zapnutý
a strop rešerše 0,30 USD na požadavek. Vypnutý výslech znamená, že `brief.needs_brief` nikdy nebudí srdce.
Mění ho jen člověk, nebo agent při plné autonomii (`require_authority` v routě); tady se jen ověří tělo a projekt.
Zápis zachová ostatní nastavení `settings.brain`.
"""
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id

RESEARCH_USD, MAX_RESEARCH_USD = 0.30, 5.0
DEFAULT = {"enabled": True, "researchUsd": RESEARCH_USD}
EXAMPLE = {"project": "draft", "enabled": True, "researchUsd": RESEARCH_USD}


def _usd(value):
    return type(value) in (int, float) and 0 <= value <= MAX_RESEARCH_USD


def read(service, pid):
    """`{enabled, researchUsd}`; neznámý projekt, chybějící složka i poškozený soubor = výchozí (zapnuto, 0,30)."""
    try:
        folder = service.folder(pid)
        brain = folder.read().get("settings", {}).get("brain") if folder.exists() else None
    except (ValueError, OSError, AttributeError):
        brain = None
    stored = brain.get("brief") if isinstance(brain, dict) else None
    if not isinstance(stored, dict):
        return dict(DEFAULT)
    return {"enabled": stored.get("enabled") is not False,
            "researchUsd": float(stored["researchUsd"]) if _usd(stored.get("researchUsd")) else RESEARCH_USD}


def _project(service, pid):
    if not isinstance(pid, str) or (pid != "draft" and not valid_id(pid)):
        raise invalid("Neplatný identifikátor projektu.", f"Příklad: {EXAMPLE}.")
    if not service.project_exists(pid):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "Zkontrolujte ID projektu v ?project=.")
    return pid


def get(service, pid):
    """`GET /api/brain/brief-setting?project=`: `{project, enabled, researchUsd}`, čte ho kdokoli."""
    return {"project": _project(service, pid), **read(service, pid)}


def write(service, payload):
    """Zapne nebo vypne výslech a nastaví strop rešerše; volá jen routa za `require_authority`.
    Tělo `{project, enabled, researchUsd?}`; chybějící `researchUsd` nechá uložený strop."""
    keys = set(payload) if isinstance(payload, dict) else set()
    if not {"project", "enabled"} <= keys <= {"project", "enabled", "researchUsd"} or type(payload["enabled"]) is not bool:
        raise invalid(f"Tělo je {{project, enabled: true | false, researchUsd?: 0–{MAX_RESEARCH_USD}}}.",
                      f"Příklad: {EXAMPLE}.")
    if "researchUsd" in payload and not _usd(payload["researchUsd"]):
        raise invalid(f"researchUsd je číslo 0–{MAX_RESEARCH_USD} (USD na požadavek).", f"Příklad: {EXAMPLE}.")
    pid = _project(service, payload["project"])
    with service.lock_for(pid):
        folder = service.folder(pid)
        if not folder.exists():
            raise GateError(409, "project_folder_missing", "Projekt nemá složku s project.json; nastavení nelze uložit.",
                            "Otevřete projekt v UI OPORY, aby se jeho složka založila, a zkuste to znovu.")
        brain = folder.read().get("settings", {}).get("brain")
        brain = brain if isinstance(brain, dict) else {}
        value = {"enabled": payload["enabled"],
                 "researchUsd": float(payload.get("researchUsd", read(service, pid)["researchUsd"]))}
        folder.update(settings={"brain": {**brain, "brief": value}})
    return get(service, pid)
