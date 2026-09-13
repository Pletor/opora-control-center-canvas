"""Atomický ukazatel na soukromé výstupy uvnitř jediného projektu."""
import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from pathlib import Path

from backend.workspace_sources import reparse

LOCK = threading.RLock()
DIRECTORIES = {'graphify': 'graphify-out', 'archify': 'docs/architecture/archify'}
SIGNALS = {'graphify': 'graphify-out/opora-receipt.json', 'archify': 'docs/architecture/archify/deliver-receipt.json'}


class MapArtifactError(ValueError):
    """Kontrolovaná chyba projektových artefaktů, nikoli interní TypeError API."""


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


def signal_hash(root, tool):
    path = contained(root, SIGNALS[tool])
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    if len(data) > 512 * 1024:
        raise ValueError('Potvrzení mapy je příliš velké.')
    return hashlib.sha256(data).hexdigest()


def pointer(root):
    path = contained(root, '.opora-map-refresh/current.json')
    try:
        with path.open('rb') as stream:
            data = stream.read(16385)
    except FileNotFoundError:
        return {}
    if len(data) > 16384:
        raise ValueError('Ukazatel mapy je příliš velký.')
    result = json.loads(data)
    if not isinstance(result, dict):
        raise MapArtifactError('Neplatný ukazatel mapy.')
    return result


def artifact_root(root, tool):
    with LOCK:
        entry = pointer(root).get(tool)
        if not entry:
            return root
        if not isinstance(entry, dict) or not re.fullmatch(r'[a-f0-9]{32}', str(entry.get('version', ''))):
            raise ValueError('Neplatná verze mapy.')
        # Nový ruční výstup původního nástroje má přednost před předchozí automatikou.
        if entry.get('signal') != signal_hash(root, tool):
            return root
        selected = contained(root, '.opora-map-refresh/versions/' + entry['version'])
        if not selected.is_dir():
            raise ValueError('Uložená verze mapy chybí.')
        return selected


def publish(root, revision, outputs):
    if not re.fullmatch(r'[a-f0-9]{40}', revision) or not outputs or set(outputs) - set(DIRECTORIES):
        raise ValueError('Neplatné výstupy aktualizace map.')
    with LOCK:
        current = pointer(root)
        version = uuid.uuid4().hex
        target = contained(root, '.opora-map-refresh/versions/' + version)
        target.mkdir(parents=True, exist_ok=False)
        (target / '.owner.json').write_text(json.dumps({'format':'opora-maps-v1','version':version}), encoding='utf-8')
        for tool, source in outputs.items():
            destination = contained(target, DIRECTORIES[tool])
            destination.mkdir(parents=True)
            files = ([Path(source) / name for name in ('graph.json', 'graph.html', 'GRAPH_REPORT.md', 'opora-receipt.json')]
                     if tool == 'graphify' else [p for p in Path(source).rglob('*') if p.is_file()])
            if not files or len(files) > 50 or sum(p.stat().st_size for p in files) > 64 * 1024 * 1024:
                raise ValueError('Výstupy mapy překročily limit.')
            for path in files:
                if reparse(path):
                    raise ValueError('Výstup nástroje obsahuje odkaz.')
                relative = path.relative_to(source).as_posix()
                out = contained(destination, relative)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, out)
            if tool == 'graphify':
                # Standardní Graphify cesta zůstává aktuální také pro CLI agenty.
                alias = contained(root, 'graphify-out')
                alias.mkdir(exist_ok=True)
                for name in ('graph.json', 'graph.html', 'GRAPH_REPORT.md', 'opora-receipt.json'):
                    data = (destination / name).read_bytes()
                    pending = contained(root, 'graphify-out/' + name + '.refresh-tmp')
                    pending.write_bytes(data)
                    os.replace(pending, contained(root, 'graphify-out/' + name))
            current[tool] = {'version': version, 'revision': revision, 'signal': signal_hash(root, tool)}
        pending = contained(root, '.opora-map-refresh/current.tmp')
        pending.write_text(json.dumps(current), encoding='utf-8')
        os.replace(pending, contained(root, '.opora-map-refresh/current.json'))
        # Archiv vlastní automatika; uchovává aktivní verze a tři nejnovější.
        versions = target.parent
        retained = {entry['version'] for entry in current.values()}
        owned = sorted((p for p in versions.iterdir() if re.fullmatch(r'[a-f0-9]{32}', p.name) and p.is_dir() and not reparse(p)), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in owned[3:]:
            if old.name not in retained and (old / '.owner.json').is_file():
                owner = json.loads((old / '.owner.json').read_text(encoding='utf-8'))
                if owner == {'format':'opora-maps-v1','version':old.name}:
                    shutil.rmtree(old)
