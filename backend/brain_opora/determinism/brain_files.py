"""Soubory složky `brain/` projektu, které čte snímek (docs/brain-heart.md §3a, §3b): zprávy, deník a skripty dílny.

`messages.jsonl` drží zprávy člověka `{at, workspace, text}` a u předaných relé navíc `via` (jméno relace
pracovníka, docs/brain-heart-orchestrator.md §8; supervisor je připíše dřív, než vstup zařadí) a u stejné věty
jako dřívější `duplicate` (ID vstupu vstupní brány; taková zpráva srdce nebudí ani po restartu),
`batches.jsonl` píše dávka srdce (`heart/batch.py`). Leží tu, ne v `heart/`, protože je čte i determinismus
(snímek) a ten srdce importovat nesmí. Nečitelný soubor nebo poškozený řádek = nic, nikdy výjimka.
`active_workspace.json` `{workspace, at}` zapíše nástroj srdce po přijatém plánu (docs/brain-heart-orchestrator.md §9).
"""
import ast
import json
from pathlib import Path

MESSAGES, JOURNAL = "messages.jsonl", "batches.jsonl"
ACTIVE = "active_workspace.json"  # prostor posledního přijatého plánu srdce (heart/opora_heart.py ACTIVE)
SCRIPTS = Path("dilna") / "scripts"  # skripty srdce (§3b); první řádek docstringu říká, co dělají


def brain_dir(service, project):
    """Složka `brain/` projektu (vedle `project.json`)."""
    return Path(service.folder(project).path) / "brain"


def active_workspace(brain):
    """Prostor posledního plánu, který srdce přijalo; chybějící nebo nečitelný soubor = None."""
    try:
        value = json.loads((Path(brain) / ACTIVE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    workspace = value.get("workspace") if isinstance(value, dict) else None
    return workspace if isinstance(workspace, str) and workspace else None


def append_message(brain, at, workspace, text, via=None, duplicate=None):
    """Připíše zprávu člověka jako jeden řádek JSON (`via` jen u relé, `duplicate` = ID vstupu brány `ie_…`
    u stejné věty, která srdce nebudí); vrací zapsaný záznam."""
    entry = ({"at": at, "workspace": workspace, "text": text} | ({"via": via} if via else {})
             | ({"duplicate": duplicate} if duplicate else {}))
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


def _last(found, last):
    if last is None:
        return found
    return found[-last:] if last > 0 else []


def messages(brain, workspace, last=5):
    """Posledních `last` zpráv člověka v pracovním prostoru (nejnovější poslední); `None` = všechny.
    `workspace` None = zprávy všech prostorů (dohánění po startu supervisoru)."""
    found = [entry for entry in _entries(Path(brain) / MESSAGES)
             if workspace in (None, entry.get("workspace")) and isinstance(entry.get("text"), str)]
    return _last(found, last)


def journal(brain, last=5):
    """Posledních `last` záznamů dávek srdce (nejnovější poslední); `None` = všechny."""
    return _last(_entries(Path(brain) / JOURNAL), last)


def _first_doc_line(path):
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, SyntaxError):
        return ""
    return (doc or "").strip().splitlines()[0].strip() if (doc or "").strip() else ""


def scripts(brain, last=15):
    """Skripty dílny `[(jméno bez .py, první řádek docstringu)]` podle jména, nejvýš `last`."""
    try:
        found = sorted(path for path in (Path(brain) / SCRIPTS).glob("*.py") if path.is_file())
    except OSError:
        return []
    return [(path.stem, _first_doc_line(path)) for path in found[:max(last, 0)]]
