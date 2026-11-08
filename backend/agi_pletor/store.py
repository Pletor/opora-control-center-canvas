"""Rozhovor s Pletorem a jeho rozhodnutí na disku (jen text, žádná tajemství).

- `<data>/pletor/messages.jsonl`: řádek `{at, project, workspace, role: human | pletor | heart, text}` za každou zprávu (heart = odpověď srdce na otázku Pletora).
- `<data>/projects/<id>/brain/pletor_decisions.jsonl`: rozhodnutí z akce `vault_note` (shortcut, viz README).
- `<data>/pletor/settings.json`: zvolený mozek a model každého mozku `{brain, claudeModel, codexModel, ollamaModel}`, jeden pro aplikaci (P2).
"""
import json
from pathlib import Path

MESSAGES = "messages.jsonl"
DECISIONS = "pletor_decisions.jsonl"
SETTINGS = "settings.json"


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


def settings(folder):
    """Volba mozku pro celou aplikaci `{brain: claude | codex | ollama, claudeModel, codexModel, ollamaModel}`;
    chybějící nebo vadný soubor = claude, starý soubor bez modelů Claude a Codexu se čte dál;
    `claudeEffort` a `codexEffort` None = výchozí."""
    try:
        value = json.loads((Path(folder) / SETTINGS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    value = value if isinstance(value, dict) else {}
    models = {key: value.get(key) if isinstance(value.get(key), str) and value.get(key) else None
              for key in ("claudeModel", "codexModel", "ollamaModel", "claudeEffort", "codexEffort")}
    brain = value.get("brain")
    brain = "codex" if brain == "codex" else "ollama" if brain == "ollama" and models["ollamaModel"] else "claude"
    return {"brain": brain, **models, "claudeModel": models["claudeModel"] or "sonnet"}


def save_settings(folder, value):
    path = Path(folder) / SETTINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return value
