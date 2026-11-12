"""Přepínač brány projektu (docs/brain-gate.md §1): `settings.brain = {gate, since?, by?, autonomyPassesGate?}` v `project.json`.

Leží vedle `settings.agentAutonomy` a čte se i zapisuje stejně jako `project_hub.agent_autonomy` /
`set_agent_autonomy`: chybějící nebo poškozená hodnota znamená vypnuto. Zapíná a vypíná ho jen člověk;
tuhle podmínku hlídá routa (`require_human`), tady se jen ověří tělo a projekt.
"""
from datetime import UTC, datetime

from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.graph import valid_id

EXAMPLE = {"project": "draft", "enabled": True, "autonomyPassesGate": True}
PASSES = "autonomyPassesGate"  # při plné autonomii agentů projektu zeď agenta pustí (docs/brain-gate.md §3)


def read(service, pid):
    """`{gate, since?, by?}`; neznámý projekt, chybějící složka i poškozený soubor = `{gate: False}`."""
    try:
        folder = service.folder(pid)
        stored = folder.read().get("settings", {}).get("brain") if folder.exists() else None
    except (ValueError, OSError, AttributeError):
        stored = None
    if not isinstance(stored, dict):
        return {"gate": False}
    passes = {PASSES: True} if stored.get(PASSES) is True else {}
    if stored.get("gate") is not True:
        return {"gate": False, **passes}
    return {"gate": True, **passes, **{key: stored[key] for key in ("since", "by") if isinstance(stored.get(key), str)}}


def is_on(service, pid):
    """Má projekt zapnutou bránu? Prázdné nebo neplatné ID nikdy."""
    if not isinstance(pid, str) or not pid or (pid != "draft" and not valid_id(pid)):
        return False
    return read(service, pid)["gate"]


def autonomy_passes(service, pid):
    """Pustí zeď agenta projektu? Pole je zapnuté A projekt má plnou autonomii (jediný zdroj: `ProjectHub`)."""
    return read(service, pid).get(PASSES) is True and service.project_hub.agent_autonomy(pid)["full"] is True


def answer(pid, value):
    """Tvar odpovědi rout: `{project, enabled, since?, by?}`."""
    return {"project": pid, "enabled": value["gate"],
            **{key: value[key] for key in ("since", "by", PASSES) if key in value}}


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
    if (not isinstance(payload, dict) or not {"project", "enabled"} <= set(payload) <= {"project", "enabled", PASSES}
            or type(payload["enabled"]) is not bool or type(payload.get(PASSES, False)) is not bool):
        raise invalid("Tělo je {project, enabled: true | false} a volitelně autonomyPassesGate: true | false.",
                      f"Příklad: {EXAMPLE}.")
    pid = _project(service, payload["project"])
    with service.lock_for(pid):
        folder = service.folder(pid)
        if not folder.exists():
            raise GateError(409, "project_folder_missing", "Projekt nemá složku s project.json; bránu nelze uložit.",
                            "Otevřete projekt v UI OPORY, aby se jeho složka založila, a zkuste to znovu.")
        stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
        value = {"gate": True, "since": stamp, "by": "human"} if payload["enabled"] else {"gate": False}
        stored = folder.read().get("settings", {}).get("brain")
        # Ostatní nastavení mozku (intake, brief) přežije přepnutí brány; staré since/by ne.
        stored = stored if isinstance(stored, dict) else {}
        rest = {key: item for key, item in stored.items() if key not in ("gate", "since", "by")}
        # autonomyPassesGate bez pole v těle zůstává; vypnutí brány ho nemaže.
        passes = {PASSES: payload[PASSES]} if PASSES in payload else {}
        folder.update(settings={"brain": {**rest, **value, **passes}})
    return answer(pid, read(service, pid))
