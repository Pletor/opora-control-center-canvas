"""Stabilní sada map na pevných cestách hlavního projektu, přepisovaná na místě (docs/mapy-projektu.md)."""
import os
import re
import threading
from pathlib import Path

from backend.integrations.gitio import git
from backend.project.maps.map_git_exclude import ensure_excluded
from backend.project.workspace.workspace_sources import reparse

LOCK = threading.RLock()
DIRECTORIES = {'graphify': 'graphify-out'}
# Jediné soubory, které se publikují; ostatní mezivýstupy zůstávají v dočasné složce běhu.
FILES = {
    'graphify': ('graph.json', 'graph.html', 'GRAPH_REPORT.md', 'opora-receipt.json'),
}
# Podle tohoto souboru se pozná, že sada nástroje v projektu existuje.
SIGNALS = {'graphify': 'graphify-out/graph.json'}
MAX_FILE = 32 * 1024 * 1024


class ArtifactUnavailable(ValueError):
    pass


def contained(root, relative):
    parts = relative.split('/')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', part) or part in ('.', '..') for part in parts):
        raise ValueError('Neplatná cesta uložené mapy.')
    target = root
    for part in parts:
        target = target / part
        try:
            if reparse(target):
                raise ValueError('Úložiště map nesmí být odkaz ani junction.')
        except FileNotFoundError:
            pass
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Úložiště map opouští projekt.')
    return target


def _canonical_root(root):
    if not root.is_dir() or reparse(root) or root.resolve() != root.absolute():
        raise ArtifactUnavailable('Zdroj projektu není bezpečný dostupný adresář.')
    return root.resolve()


def main_project_root(service, project):
    item = service.project_hub.settings(project)['project']  # settings čte snímkem projektu sama
    if not item.get('sourcePath'):
        raise ArtifactUnavailable('Projekt nemá připojený zdrojový adresář.')
    root = _canonical_root(Path(item['sourcePath']))
    # První záznam Git worktree list je hlavní pracovní strom, nikoli vybraná větev.
    if (root / '.git').exists():
        records = git(root, 'worktree', 'list', '--porcelain', '-z', timeout=3)
        if not isinstance(records, str):
            raise ArtifactUnavailable('Hlavní pracovní strom nelze určit.')
        first = records.split('\0', 1)[0]
        if not first.startswith('worktree ') or len(first) > 4096:
            raise ArtifactUnavailable('Hlavní pracovní strom nelze určit.')
        main = _canonical_root(Path(first.removeprefix('worktree ')))
        args = ('rev-parse', '--path-format=absolute', '--git-common-dir')
        source_git, main_git = git(root, *args, timeout=3), git(main, *args, timeout=3)
        if not isinstance(source_git, str) or not isinstance(main_git, str):
            raise ArtifactUnavailable('Identitu pracovního stromu nelze ověřit.')
        if Path(source_git).resolve() != Path(main_git).resolve():
            raise ArtifactUnavailable('Pracovní stromy nepatří ke stejnému projektu.')
        root = main
    return root


def missing_tools(root):
    """Nástroje, jejichž stabilní sada v projektu chybí; takový projekt dostane počáteční běh."""
    missing = []
    for tool, relative in SIGNALS.items():
        try:
            if not contained(root, relative).is_file():
                missing.append(tool)
        except ValueError:
            continue
    return missing


def _payloads(tool, source):
    payloads = {}
    for name in FILES[tool]:
        path = Path(source) / name
        if not path.is_file() or reparse(path):
            raise ValueError('Běh nedodal úplnou sadu mapy.')
        if path.stat().st_size > MAX_FILE:
            raise ValueError('Výstupy mapy překročily limit.')
        payloads[name] = path.read_bytes()
    return payloads


def publish(root, revision, outputs):
    """Přepíše stabilní soubory na místě. Každý soubor jde přes `<name>.tmp` a `os.replace`."""
    if not re.fullmatch(r'[a-f0-9]{40}', revision) or not outputs or set(outputs) - set(DIRECTORIES):
        raise ValueError('Neplatné výstupy aktualizace map.')
    # Nejdřív se přečte celá sada; neúplný běh nepřepíše ani jeden soubor.
    prepared = {tool: _payloads(tool, source) for tool, source in outputs.items()}
    with LOCK:
        for tool, payloads in prepared.items():
            folder = contained(root, DIRECTORIES[tool])
            folder.mkdir(exist_ok=True)
            ensure_excluded(root, DIRECTORIES[tool])
            for name, data in payloads.items():
                destination = contained(root, DIRECTORIES[tool] + '/' + name)
                pending = contained(root, DIRECTORIES[tool] + '/' + name + '.tmp')
                pending.write_bytes(data)
                os.replace(pending, destination)
