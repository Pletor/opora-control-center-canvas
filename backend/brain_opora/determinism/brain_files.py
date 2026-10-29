"""Soubory složky `brain/` projektu, které čte snímek (docs/brain-heart.md §3a): zprávy člověka a deník dávek.

`messages.jsonl` drží zprávy člověka `{at, workspace, text}` (supervisor je připíše dřív, než vstup zařadí),
`batches.jsonl` píše dávka srdce (`heart/batch.py`). Leží tu, ne v `heart/`, protože je čte i determinismus
(snímek) a ten srdce importovat nesmí. Nečitelný soubor nebo poškozený řádek = nic, nikdy výjimka.
"""
import json
from pathlib import Path

MESSAGES, JOURNAL = "messages.jsonl", "batches.jsonl"


def brain_dir(service, project):
    """Složka `brain/` projektu (vedle `project.json`)."""
    return Path(service.folder(project).path) / "brain"


def append_message(brain, at, workspace, text):
    """Připíše zprávu člověka jako jeden řádek JSON; vrací zapsaný záznam."""
    entry = {"at": at, "workspace": workspace, "text": text}
    brain = Path(brain)
    brain.mkdir(parents=True, exist_ok=True)
    with (brain / MESSAGES).open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _entries(path):
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return []
    entries = []
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries


def messages(brain, workspace, last=5):
    """Posledních `last` zpráv člověka v pracovním prostoru (nejnovější poslední)."""
    found = [entry for entry in _entries(Path(brain) / MESSAGES)
             if entry.get("workspace") == workspace and isinstance(entry.get("text"), str)]
    return found[-last:] if last > 0 else []


def journal(brain, last=5):
    """Posledních `last` záznamů dávek srdce (nejnovější poslední)."""
    found = _entries(Path(brain) / JOURNAL)
    return found[-last:] if last > 0 else []
