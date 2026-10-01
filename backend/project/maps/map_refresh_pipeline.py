"""Sestavení map z neměnného main v dočasné složce a publikace stabilní sady do téhož projektu."""
import json
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from backend.project.maps.graphify_runtime import generate_graph, writable
from backend.project.maps.map_artifacts import publish
from backend.project.maps.map_refresh_archify import build_archify
from backend.project.maps.map_refresh_snapshot import snapshot_main


def build_maps(job, manager):
    root = Path(job['root'])
    if not manager.current(job):
        raise ValueError('Revize main se změnila; starý běh nebyl spuštěn.')
    output = writable(root, 'graphify-out')
    output.mkdir(exist_ok=True)
    with writable(root, 'graphify-out/opora-build.lock').open('a+b') as lock:
        lock.seek(0)
        import os
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError('Jiný běh právě aktualizuje mapy tohoto projektu.') from exc
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(prefix='opora-map-refresh-') as directory:
            work = Path(directory)
            source = work / 'source'
            snapshot_main(root, job['revision'], source)
            manager.phase(job, 'graphify')
            proxy = SimpleNamespace(lock=threading.RLock(), project_hub=SimpleNamespace(
                settings=lambda project: {'project': {'sourcePath': str(source)}}))
            generate_graph(proxy, job['project'])
            receipt = source / 'graphify-out/opora-receipt.json'
            meta = json.loads(receipt.read_text(encoding='utf-8'))
            meta['sourceRevision'] = job['revision']
            receipt.write_text(json.dumps(meta), encoding='utf-8')
            outputs = {'graphify': source / 'graphify-out'} if 'graphify' in job['tools'] else {}
            if 'archify' in job['tools']:
                manager.phase(job, 'archify')
                destination = work / 'archify'
                build_archify(source, destination, job['revision'], cancel=manager.stop)
                # Publikuje se jen pět souborů ze smlouvy; validate receipt a evidence zůstanou v temp.
                outputs['archify'] = destination
            manager.phase(job, 'publishing')
            # Provider neběží v transakci. Krátká publikace znovu ověřuje owner, root i SHA.
            with manager.lock, manager.db:
                manager.db.execute('BEGIN IMMEDIATE')
                if not manager.current(job):
                    raise ValueError('Main nebo projekt se změnil; starý výsledek nebyl publikován.')
                publish(root, job['revision'], outputs)
