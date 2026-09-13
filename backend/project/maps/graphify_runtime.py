"""Oddělený, časově omezený běh nainstalovaného původního Graphify CLI."""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from backend.integrations.windows_job import WindowsJob
from backend.paths import GRAPHIFY_VENV
from backend.project.maps.map_artifacts import LOCK as PUBLISH_LOCK
from backend.project.maps.map_artifacts import ArtifactUnavailable, main_project_root
from backend.project.workspace.workspace_sources import reparse

# Nejvýše jeden dražší parser na proces serveru; žádný placený model.
GATE = threading.Lock()

PUBLIC_FILES = ('graph.json', 'graph.html', 'GRAPH_REPORT.md')


def writable(root, relative):
    if not re.fullmatch(r'graphify-out(?:/[A-Za-z0-9][A-Za-z0-9_.-]{0,99})?', relative):
        raise ArtifactUnavailable('Neplatná cesta výstupu Graphify.')
    target = root
    for part in relative.split('/'):
        target = target / part
        try:
            linked = reparse(target)
        except FileNotFoundError:
            linked = False
        if linked:
            raise ArtifactUnavailable('Výstup Graphify nesmí být odkaz ani junction.')
    if not target.resolve().is_relative_to(root):
        raise ArtifactUnavailable('Výstup opouští hlavní projekt.')
    return target


def clean_environment():
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATHEXT', 'COMSPEC',
        'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA',
    }}
    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', GRAPHIFY_FOLLOW_SYMLINKS='0')
    return env


@lru_cache(maxsize=1)
def runtime():
    configured = os.environ.get('OPORA_GRAPHIFY_PYTHON')
    local = GRAPHIFY_VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    candidates = [configured] if configured else [str(local), shutil.which('python'), sys.executable]
    for candidate in dict.fromkeys(candidates):
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run([candidate, '-I', '-c', "import importlib.metadata;print(importlib.metadata.version('graphifyy'))"],
                                    cwd=tempfile.gettempdir(), env=clean_environment(), capture_output=True, timeout=5, check=False)
            if result.returncode == 0 and result.stdout.strip() == b'0.9.24':
                return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    raise ArtifactUnavailable('Chybí graphifyy==0.9.24. Nastavte OPORA_GRAPHIFY_PYTHON podle projektového návodu.')


def run_original(root, output):
    command = [runtime(), '-I', '-X', 'utf8', str(Path(__file__).with_name('graphify_worker.py').resolve()), str(root), str(output)]
    job = WindowsJob() if os.name == 'nt' else None
    process = None
    with (output / 'graphify.log').open('wb') as log:
        try:
            process = subprocess.Popen(command, cwd=output, env=clean_environment(), stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=job.CREATE_SUSPENDED | job.CREATE_NO_WINDOW if job else 0,
                                       start_new_session=job is None)
            if job:
                job.assign_and_resume(process)
            process.wait(timeout=120)
            if process.returncode:
                raise ArtifactUnavailable('Graphify nedokončil analýzu. Zkontrolujte .graphifyignore a limit 500 souborů / 32 MiB.')
        except subprocess.TimeoutExpired as exc:
            raise ArtifactUnavailable('Graphify překročil limit 120 sekund; předchozí graf zůstává uložený.') from exc
        finally:
            if job:
                job.close()
            elif process and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            if process:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)


def generate_graph(service, project):
    if not GATE.acquire(blocking=False):
        raise ArtifactUnavailable('Graphify právě vytváří graf. Počkejte na dokončení a zkuste načíst výsledek.')
    try:
        root = main_project_root(service, project)
        folder = writable(root, 'graphify-out')
        folder.mkdir(exist_ok=True)
        # Zámek OS se uvolní i po pádu; dva procesy nemohou publikovat současně.
        lock_path = writable(root, 'graphify-out/opora-build.lock')
        with lock_path.open('a+b') as lock:
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise ArtifactUnavailable('Graf tohoto projektu právě vytváří jiný proces.') from exc
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with tempfile.TemporaryDirectory(prefix='opora-graphify-') as scratch:
                output = Path(scratch)
                run_original(root, output)
                produced = output / 'graphify-out'
                payloads = {}
                for name in PUBLIC_FILES:
                    path = produced / name
                    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
                        raise ArtifactUnavailable('Graphify nedodal úplné výstupy v povolené velikosti.')
                    payloads[name] = path.read_bytes()
                graph = json.loads(payloads['graph.json'])
                if not graph.get('nodes'):
                    raise ArtifactUnavailable('Graphify vytvořil prázdný graf; předchozí nebyl nahrazen.')
                if main_project_root(service, project) != root:
                    raise ArtifactUnavailable('Zdroj projektu se během běhu změnil; výstup nebyl publikován.')
                receipt = {'version': '0.9.24', 'repository': 'https://github.com/Graphify-Labs/graphify',
                           'generatedAt': datetime.now(UTC).isoformat(),
                           'scope': 'Původní Graphify --code-only; lokální AST, bez modelu; respektuje .graphifyignore.',
                           'hashes': {name: hashlib.sha256(payloads[name]).hexdigest() for name in ('graph.html', 'graph.json')}}
                log = (output / 'graphify.log').read_text(encoding='utf-8', errors='replace')
                receipt['warnings'] = re.findall(r'^\s*warning: \d+ source file\(s\) produced zero nodes[^\n]*', log, re.MULTILINE)[:10]
                receipt['corpus'] = json.loads(log.splitlines()[0])
                payloads['opora-receipt.json'] = json.dumps(receipt, ensure_ascii=False).encode('utf-8')
                # Veřejné bajty zůstávají přesně tak, jak je vygenerovalo původní CLI.
                with PUBLISH_LOCK:
                    for name, data in payloads.items():
                        destination = writable(root, 'graphify-out/' + name)
                        temporary = writable(root, 'graphify-out/opora-' + name + '.tmp')
                        temporary.write_bytes(data)
                        writable(root, 'graphify-out/' + name)
                        os.replace(temporary, destination)
    finally:
        GATE.release()
