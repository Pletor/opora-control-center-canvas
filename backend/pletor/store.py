"""Rozhovor s Pletorem a jeho rozhodnutí na disku (jen text, žádná tajemství).

- `<data>/pletor/messages.jsonl`: řádek `{at, project, workspace, role: human | pletor, text}` za každou zprávu.
- `<data>/projects/<id>/brain/pletor_decisions.jsonl`: rozhodnutí z akce `vault_note` (shortcut, viz README).
"""
import json
from pathlib import Path

MESSAGES = "messages.jsonl"
DECISIONS = "pletor_decisions.jsonl"


def _append(path, entry):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def append_message(folder, at, project, workspace, role, text):
    return _append(Path(folder) / MESSAGES, {"at": at, "project": project, "workspace": workspace, "role": role,
                                             "text": text})


def messages(folder, project, workspace, last=50):
    """Posledních `last` zpráv projektu a prostoru `[{role, text, at}]`, nejnovější poslední; vadné řádky přeskočí."""
    try:
        lines = (Path(folder) / MESSAGES).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    found = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("project") == project and entry.get("workspace") == workspace:
            found.append({"role": entry.get("role"), "text": entry.get("text"), "at": entry.get("at")})
    return found[-last:]


def append_decision(brain, at, workspace, text):
    return _append(Path(brain) / DECISIONS, {"at": at, "workspace": workspace, "text": text, "by": "pletor"})
