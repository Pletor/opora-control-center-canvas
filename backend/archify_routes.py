"""Mapa čte doručené Archify HTML hlavního projektu; nic negeneruje ani nespouští."""

import hashlib
import json
import re
import subprocess
from pathlib import Path, PureWindowsPath

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.gitio import git
from backend.map_artifacts import LOCK, artifact_root
from backend.workspace_sources import WorkspaceSources, reparse

DIRECTORY = 'docs/architecture/archify'
MAX_HTML = 4 * 1024 * 1024
MAX_JSON = 512 * 1024
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$')


class ArtifactUnavailable(ValueError):
    pass


def _canonical_root(root):
    if not root.is_dir() or reparse(root) or root.resolve() != root.absolute():
        raise ArtifactUnavailable('Zdroj projektu není bezpečný dostupný adresář.')
    return root.resolve()


def main_project_root(service, project):
    with service.lock:
        item = service.project_hub.settings(project)['project']
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


def _read(sources, root, name, limit):
    root = artifact_root(root, 'archify')
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ArtifactUnavailable('Neplatný název souboru mapy.')
    relative = DIRECTORY + '/' + name
    target = sources.target(root, relative)
    if not target.is_file():
        raise ArtifactUnavailable('Mapa musí být běžný soubor.')
    with target.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ArtifactUnavailable('Soubor mapy překračuje bezpečný limit.')
    sources.target(root, relative)
    return data


def _json(data):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ArtifactUnavailable('Soubor potvrzení nebo specifikace není platný JSON.') from exc
    if not isinstance(value, dict):
        raise ArtifactUnavailable('Potvrzení nebo specifikace musí být objekt.')
    return value


def _digest(data):
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def load_artifact(service, project):
    with LOCK:
        return _load_artifact(service, project)


def _load_artifact(service, project):
    root = main_project_root(service, project)
    sources = WorkspaceSources(service)
    receipt = _json(_read(sources, root, 'deliver-receipt.json', MAX_JSON))
    if receipt.get('ok') is not True or receipt.get('command') != 'deliver':
        raise ArtifactUnavailable('Chybí úspěšné potvrzení doručení Archify.')
    # Cesty z potvrzení nejsou oprávnění číst filesystem; použije se jen bezpečný basename.
    output = receipt.get('output')
    input_path = receipt.get('input')
    if not isinstance(output, str) or not isinstance(input_path, str):
        raise ArtifactUnavailable('Potvrzení neuvádí soubory mapy.')
    name, spec_name = PureWindowsPath(output).name, PureWindowsPath(input_path).name
    if not name.endswith('.html') or not spec_name.endswith('.json'):
        raise ArtifactUnavailable('Potvrzení neodkazuje na HTML a JSON.')
    html = _read(sources, root, name, MAX_HTML)
    specification = _read(sources, root, spec_name, MAX_JSON)
    if _digest(html) != receipt.get('artifact') or _digest(specification) != receipt.get('specification'):
        raise ArtifactUnavailable('HTML nebo JSON neodpovídá potvrzení doručení. Vygenerujte úplnou novou sadu.')
    spec = _json(specification)
    if '<svg' not in html.decode('utf-8').lower():
        raise ArtifactUnavailable('Soubor neobsahuje doručený diagram SVG.')
    validation = receipt.get('validation')
    if not isinstance(validation, dict) or validation.get('errors') != 0:
        raise ArtifactUnavailable('Potvrzení neprokazuje úspěšnou validaci.')
    browser = {'status': 'unavailable', 'coverage': []}
    try:
        proof = _json(_read(sources, root, 'visual-check-receipt.json', MAX_JSON))
        if proof.get('artifact', {}).get('sha256') == _digest(html)['sha256']:
            measurements = proof.get('containment', {}).get('viewports', [])
            browser = {'status': proof.get('status', 'unknown'), 'coverage': [
                {k: row.get(k) for k in ('width', 'height', 'theme', 'ok')}
                for row in measurements[:24] if isinstance(row, dict)
            ]}
    except (FileNotFoundError, ArtifactUnavailable, AttributeError, TypeError):
        pass
    document = ''
    try:
        document = _read(sources, root, 'SPEC.md', 128 * 1024).decode('utf-8')
    except FileNotFoundError:
        pass
    revision = re.search(r'Revize repa:\s*`([a-f0-9]{40})`', document)
    revision = revision.group(1) if revision else None
    # Starý commit je důkaz rozdílu; stejný commit sám neprokazuje čistotu živých souborů.
    current = git(root, 'rev-parse', 'HEAD', timeout=3, optional=True) if (root / '.git').exists() else None
    freshness = 'changed' if revision and current and revision != current else 'unknown'
    return {
        'project': project, 'sourceRoot': str(root), 'sourcePath': (artifact_root(root, 'archify') / DIRECTORY / name).relative_to(root).as_posix(),
        'fileName': name, 'specificationName': spec_name, 'html': html.decode('utf-8'),
        'specificationJson': specification.decode('utf-8'), 'specificationDocument': document,
        'artifact': _digest(html), 'specification': _digest(specification),
        'validation': {k: validation.get(k) for k in ('checksPassed', 'checkCount', 'compositionProfile', 'errors', 'warnings')},
        'browserEvidence': browser, 'sourceRevision': revision, 'freshness': freshness,
        'counts': {k: len(spec.get(k, [])) if isinstance(spec.get(k, []), list) else None
                   for k in ('components', 'connections', 'boundaries')},
    }


def create_archify_router(service):
    router = APIRouter(prefix='/api/archify', tags=['archify'])

    @router.get('/artifact')
    def artifact(project: str = Query(min_length=1, max_length=64)):
        try:
            value = load_artifact(service, project)
            return JSONResponse(value, headers={'Cache-Control': 'no-store'})
        except FileNotFoundError:
            return JSONResponse({'error': 'Mapa zatím chybí. Spusťte Archify nad hlavním projektem a uložte výstupy do ' + DIRECTORY + '.'}, status_code=404)
        except ArtifactUnavailable as exc:
            return JSONResponse({'error': str(exc)}, status_code=409)
        except (ValueError, KeyError, OSError, UnicodeError, subprocess.SubprocessError):
            return JSONResponse({'error': 'Mapu tohoto projektu nelze bezpečně načíst.'}, status_code=409)

    return router
