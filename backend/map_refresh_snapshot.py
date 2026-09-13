"""Bezpečný textový snapshot jedné konkrétní revize; žádný checkout cizího kódu."""
import io
import os
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from backend.gitio import git

EXCLUDED = {'.git', '.opora', '.opora-map-refresh', '.claude', '.agents', '.worktrees', '.data',
            'vendor', 'node_modules', 'dist', 'build', 'graphify-out', 'evidence', 'test-results'}
EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json', '.toml', '.yaml', '.yml',
              '.md', '.sql', '.go', '.rs', '.java', '.cs', '.c', '.cpp', '.h', '.html', '.css', '.vue', '.svelte'}
OMITTED_NAMES = {'claude.md', 'agents.md', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
                 'credentials.json', 'service-account.json', '.npmrc', '.pypirc'}


def safe_relative(name):
    if not isinstance(name, str) or not name or len(name.encode('utf-8')) > 2048:
        raise ValueError('Neplatná cesta snapshotu.')
    parts = name.split('/')
    for part in parts:
        if (part in ('', '.', '..') or len(part.encode('utf-8')) > 240 or part.endswith((' ', '.'))
                or re.search(r'[\x00-\x1f\\:<>"|?*]', part)
                or re.fullmatch(r'(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)):
            raise ValueError('Nepřenosná cesta snapshotu.')
    return PurePosixPath(name)


def snapshot_main(root, revision, target):
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Neplatná revize main.')
    records = git(root, 'ls-tree', '-r', '-l', '-z', revision, timeout=15)
    selected, total = [], 0
    for record in records.split('\0'):
        if not record:
            continue
        header, name = record.split('\t', 1)
        mode, kind, _oid, size = header.split()
        path = safe_relative(name)
        if mode not in ('100644', '100755') or kind != 'blob':
            continue
        if any(part in EXCLUDED or part.startswith('.venv') for part in path.parts):
            continue
        if path.name.casefold().startswith('.env') or path.name.casefold() in OMITTED_NAMES:
            continue
        if path.suffix.lower() not in EXTENSIONS and path.name not in ('.gitignore', '.graphifyignore', 'Dockerfile'):
            continue
        size = int(size)
        if size > 1024 * 1024:
            raise ValueError('Zdrojový soubor překračuje 1 MiB; upravte rozsah projektu.')
        total += size
        selected.append(name)
    if not selected or len(selected) > 800 or total > 8 * 1024 * 1024:
        raise ValueError('Snapshot vyžaduje 1–800 textových souborů a nejvýše 8 MiB.')
    # Shell se nepoužívá; každý název je samostatný argument až za --.
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    command = ['git', '-c', 'core.hooksPath=' + str(Path(__file__).with_name('disabled-hooks')),
               '-c', 'core.fsmonitor=false', '-C', str(root), 'archive', '--format=zip', revision, '--', *selected]
    result = subprocess.run(command, check=True, capture_output=True, env=env, timeout=30,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with zipfile.ZipFile(io.BytesIO(result.stdout)) as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if {entry.filename for entry in entries} != set(selected):
            raise ValueError('Git export vynechal soubory; neúplný snapshot nelze použít.')
        target.mkdir(parents=True, exist_ok=False)
        for entry in entries:
            path = safe_relative(entry.filename)
            data = archive.read(entry)
            if len(data) > 1024 * 1024 or b'\0' in data:
                raise ValueError('Snapshot obsahuje binární nebo příliš velký vstup.')
            data.decode('utf-8')
            output = target.joinpath(*path.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
    return selected
