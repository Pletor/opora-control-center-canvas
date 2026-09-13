"""Tenký adaptér původního Graphify. Neobsahuje extraktor ani renderer grafu."""
import hashlib
import json
import subprocess

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.archify_routes import ArtifactUnavailable, main_project_root
from backend.graphify_runtime import PUBLISH_LOCK, generate_graph
from backend.map_artifacts import artifact_root
from backend.workspace_sources import WorkspaceSources

MAX_ARTIFACT = 32 * 1024 * 1024


def read_output(service, root, name):
    root = artifact_root(root, 'graphify')
    target = WorkspaceSources(service).target(root, 'graphify-out/' + name)
    if not target.is_file():
        raise ArtifactUnavailable('Výstup Graphify není běžný soubor.')
    with target.open('rb') as stream:
        value = stream.read(MAX_ARTIFACT + 1)
    if len(value) > MAX_ARTIFACT:
        raise ArtifactUnavailable('Výstup Graphify překračuje limit 32 MiB.')
    return value


def load_graph(service, project):
    with PUBLISH_LOCK:
        return _load_graph(service, project)


def _load_graph(service, project):
    root = main_project_root(service, project)
    html = read_output(service, root, 'graph.html')
    raw = read_output(service, root, 'graph.json')
    graph = json.loads(raw)
    nodes, edges = graph.get('nodes'), graph.get('links', graph.get('edges'))
    if not isinstance(nodes, list) or not nodes or not isinstance(edges, list):
        raise ArtifactUnavailable('Graphify nevytvořil platný neprázdný graf.')
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in (
        ('graph.html', html), ('graph.json', raw))}
    receipt = {}
    try:
        candidate = json.loads(read_output(service, root, 'opora-receipt.json'))
        if candidate.get('hashes') == hashes:
            receipt = candidate
    except FileNotFoundError:
        pass
    return {
        'project': project, 'sourceRoot': str(root), 'sourcePath': 'graphify-out/graph.html',
        'html': html.decode('utf-8'), 'graphJson': raw.decode('utf-8'),
        'counts': {'nodes': len(nodes), 'edges': len(edges)}, 'hashes': hashes,
        'generatedAt': receipt.get('generatedAt'), 'version': receipt.get('version'),
        'warnings': receipt.get('warnings', []), 'corpus': receipt.get('corpus'),
        'scope': receipt.get('scope', 'Externí výstup Graphify; rozsah určil jeho autor.'),
    }


def create_graphify_router(service):
    router = APIRouter(prefix='/api/graphify', tags=['graphify'])

    @router.post('/generate')
    def generate(project: str = Query(min_length=1, max_length=64)):
        try:
            generate_graph(service, project)
            return load_graph(service, project)
        except ArtifactUnavailable as exc:
            return JSONResponse({'error': str(exc)}, status_code=409)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError):
            return JSONResponse({'error': 'Graphify tohoto projektu nelze bezpečně spustit nebo uložit.'}, status_code=409)

    @router.get('/artifact')
    def artifact(project: str = Query(min_length=1, max_length=64)):
        try:
            return load_graph(service, project)
        except FileNotFoundError:
            return JSONResponse({'error': 'Graf projektu zatím není vytvořený.'}, status_code=404)
        except ArtifactUnavailable as exc:
            return JSONResponse({'error': str(exc)}, status_code=409)
        except (ValueError, KeyError, TypeError, AttributeError, OSError, RecursionError, subprocess.SubprocessError):
            return JSONResponse({'error': 'Graf tohoto projektu nelze bezpečně načíst.'}, status_code=409)

    return router
