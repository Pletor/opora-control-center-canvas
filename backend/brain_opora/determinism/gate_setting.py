"""Přepínač brány projektu (docs/brain-gate.md §1): `settings.brain = {gate, since?, by?}` v `project.json`.

Leží vedle `settings.agentAutonomy` a čte se i zapisuje stejně jako `project_hub.agent_autonomy` /
`set_agent_autonomy`: chybějící nebo poškozená hodnota znamená vypnuto. Zapíná a vypíná ho jen člověk;
tuhle podmínku hlídá routa (`require_human`), tady se jen ověří tělo a projekt.
"""
from datetime import UTC, datetime

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id

EXAMPLE = {"project": "draft", "enabled": True}


def read(service, pid):
    """`{gate, since?, by?}`; neznámý projekt, chybějící složka i poškozený soubor = `{gate: False}`."""
    try:
        folder = service.folder(pid)
        stored = folder.read().get("settings", {}).get("brain") if folder.exists() else None
    except (ValueError, OSError, AttributeError):
        stored = None
    if not isinstance(stored, dict) or stored.get("gate") is not True:
        return {"gate": False}
    return {"gate": True, **{key: stored[key] for key in ("since", "by") if isinstance(stored.get(key), str)}}


def is_on(service, pid):
    """Má projekt zapnutou bránu? Prázdné nebo neplatné ID nikdy."""
    if not isinstance(pid, str) or not pid or (pid != "draft" and not valid_id(pid)):
        return False
    return read(service, pid)["gate"]


def answer(pid, value):
    """Tvar odpovědi rout: `{project, enabled, since?, by?}`."""
    return {"project": pid, "enabled": value["gate"], **{key: value[key] for key in ("since", "by") if key in value}}


def _project(service, pid):
    if not isinstance(pid, str) or (pid != "draft" and not valid_id(pid)):
        raise invalid("Neplatný identifikátor projektu.", "Pošlete {\"project\": \"<id>\", \"enabled\": true}.")
    if not service.project_exists(pid):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "Zkontrolujte ID projektu v ?project=.")
    return pid


def get(service, pid):
    """`GET /api/brain/gate-setting?project=`: stav přepínače, čte ho kdokoli."""
    return answer(_project(service, pid), read(service, pid))


def write(service, payload, now=None):
    """Zapne nebo vypne bránu projektu; volá jen routa za `require_human`."""
    if not isinstance(payload, dict) or set(payload) != {"project", "enabled"} or type(payload["enabled"]) is not bool:
        raise invalid("Tělo je přesně {project, enabled: true | false}.", f"Příklad: {EXAMPLE}.")
    pid = _project(service, payload["project"])
    with service.lock_for(pid):
        folder = service.folder(pid)
        if not folder.exists():
            raise GateError(409, "project_folder_missing", "Projekt nemá složku s project.json; bránu nelze uložit.",
                            "Otevřete projekt v UI OPORY, aby se jeho složka založila, a zkuste to znovu.")
        stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {"gate": True, "since": stamp, "by": "human"} if payload["enabled"] else {"gate": False}
        stored = folder.read().get("settings", {}).get("brain")
        if isinstance(stored, dict) and "intake" in stored:
            value["intake"] = stored["intake"]  # povolení Jevu vstupní brány (intake_setting.py) přežije přepnutí brány
        folder.update(settings={"brain": value})
    return answer(pid, read(service, pid))
