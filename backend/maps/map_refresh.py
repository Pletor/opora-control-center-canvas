"""Trvalý projektový trigger změn main. Jedna fronta, žádné slučování grafů."""
import json
import logging
import os
import sqlite3
import threading
import time
import uuid

from fastapi import APIRouter, Query

from backend.integrations.gitio import git
from backend.maps.map_artifacts import main_project_root

LOGGER = logging.getLogger(__name__)


class MapRefresh:
    def __init__(self, service, builder=None):
        self.service, self.builder = service, builder
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.closed = False
        self.root = service.root / 'map-refresh'
        self.root.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / 'state.sqlite', check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS config(id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL);
            INSERT OR IGNORE INTO config VALUES(1,0);
            CREATE TABLE IF NOT EXISTS projects(
                project TEXT PRIMARY KEY, root TEXT NOT NULL, observed TEXT NOT NULL,
                wanted TEXT, built TEXT, status TEXT NOT NULL, phase TEXT,
                owner TEXT, running TEXT, lease REAL, updated REAL NOT NULL, error TEXT
            );
            CREATE TABLE IF NOT EXISTS runs(
                id TEXT PRIMARY KEY, project TEXT NOT NULL, root TEXT NOT NULL,
                revision TEXT NOT NULL, status TEXT NOT NULL, started REAL NOT NULL,
                finished REAL, error TEXT
            );
        ''')
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(projects)')}
        for name, definition in {
            'auto_graphify': 'INTEGER NOT NULL DEFAULT 1', 'auto_archify': 'INTEGER NOT NULL DEFAULT 1',
            'requested_tools': '''TEXT NOT NULL DEFAULT '["graphify","archify"]' ''',
            'running_tools': 'TEXT', 'built_graphify': 'TEXT', 'built_archify': 'TEXT',
        }.items():
            if name not in columns:
                self.db.execute(f'ALTER TABLE projects ADD COLUMN {name} {definition}')
        self.db.commit()

    def enabled(self):
        with self.lock:
            return bool(self.db.execute('SELECT enabled FROM config WHERE id=1').fetchone()[0])

    def set_enabled(self, enabled, *, start=True):
        if type(enabled) is not bool:
            raise ValueError('Automatizace vyžaduje explicitní boolean.')
        with self.lock, self.db:
            self.db.execute('UPDATE config SET enabled=? WHERE id=1', (int(enabled),))
        if enabled:
            # Stávající projekty se pouze ozbrojí; zapnutí samo nespustí placené analýzy.
            self.scan(baseline=True)
            if start:
                self.start()
        else:
            self.stop.set()
        return {'enabled': enabled}

    def observe(self, project, root, revision, *, baseline=False):
        now = time.time()
        root = os.path.normcase(str(root))
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT * FROM projects WHERE project=?', (project,)).fetchone()
            if row is None or row['root'] != root:
                self.db.execute('''INSERT OR REPLACE INTO projects(project,root,observed,wanted,built,status,phase,owner,running,lease,updated,error) VALUES(?,?,?,?,NULL,?,NULL,NULL,NULL,NULL,?,NULL)''',
                                (project, root, revision, None if baseline else revision, 'watching' if baseline else 'queued', now))
            elif row['observed'] != revision:
                tools = [tool for tool in ('graphify', 'archify') if row['auto_' + tool]]
                self.db.execute('''UPDATE projects SET observed=?,wanted=?,status=?,requested_tools=?,updated=?,error=NULL WHERE project=?''',
                                (revision, revision, 'running' if row['owner'] else 'queued' if tools else 'watching', json.dumps(tools), now, project))

    def scan(self, *, baseline=False):
        if not self.enabled():
            return
        projects = self.service.bootstrap()['projects']
        for project in projects:
            try:
                root = main_project_root(self.service, project['id'])
                revision = git(root, 'rev-parse', '--verify', 'refs/heads/main', timeout=3, optional=True)
                if revision and len(revision) == 40:
                    self.observe(project['id'], root, revision, baseline=baseline)
            except (ValueError, OSError):
                continue
        active = {p['id'] for p in projects}
        with self.lock, self.db:
            for row in self.db.execute('SELECT project FROM projects').fetchall():
                if row['project'] not in active:
                    self.db.execute('DELETE FROM projects WHERE project=?', (row['project'],))

    def claim(self):
        now = time.time()
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if not self.enabled():
                return None
            # Pád procesu nesmí vytvořit nekonečný retry placeného modelu.
            self.db.execute("UPDATE runs SET status='interrupted',finished=?,error='Vypršel lease běhu.' WHERE status='running' AND id IN (SELECT owner FROM projects WHERE lease<?)", (now, now))
            self.db.execute("UPDATE projects SET status=CASE WHEN wanted!=running THEN 'queued' ELSE 'failed' END,owner=NULL,running=NULL,lease=NULL,error='Běh byl přerušen. Nový merge nebo ruční opakování jej obnoví.' WHERE owner IS NOT NULL AND lease<?", (now,))
            if self.db.execute('SELECT 1 FROM projects WHERE owner IS NOT NULL LIMIT 1').fetchone():
                return None
            row = self.db.execute("SELECT * FROM projects WHERE status='queued' ORDER BY updated,project LIMIT 1").fetchone()
            if row is None:
                return None
            # Dvě registrace worktrees téhož repozitáře nevytvářejí druhý placený běh.
            shared = self.db.execute("SELECT 1 FROM projects WHERE root=? AND project!=? AND built_graphify=? AND built_archify=? LIMIT 1", (row['root'], row['project'], row['wanted'], row['wanted'])).fetchone()
            if shared:
                self.db.execute("UPDATE projects SET status='succeeded',built=wanted WHERE project=?", (row['project'],))
                return None
            owner = uuid.uuid4().hex
            changed = self.db.execute("UPDATE projects SET status='running',phase='snapshot',owner=?,running=wanted,running_tools=requested_tools,lease=?,updated=? WHERE project=? AND owner IS NULL AND status='queued'", (owner, now + 900, now, row['project']))
            if changed.rowcount != 1:
                raise ValueError('Převzetí aktualizace se změnilo.')
            self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,NULL,NULL)', (owner, row['project'], row['root'], row['wanted'], 'running', now))
            return {'id': owner, 'project': row['project'], 'root': row['root'], 'revision': row['wanted'], 'tools': json.loads(row['requested_tools'])}

    def phase(self, job, phase):
        with self.lock, self.db:
            self.db.execute('UPDATE projects SET phase=? WHERE project=? AND owner=?', (phase, job['project'], job['id']))

    def current(self, job):
        if self.stop.is_set() or not self.enabled():
            return False
        with self.lock:
            row = self.db.execute('SELECT * FROM projects WHERE project=?', (job['project'],)).fetchone()
            if row is None or row['owner'] != job['id'] or row['wanted'] != job['revision'] or row['lease'] < time.time():
                return False
        root = main_project_root(self.service, job['project'])
        return os.path.normcase(str(root)) == job['root'] and git(root, 'rev-parse', 'refs/heads/main', timeout=3) == job['revision']

    def finish(self, job, status, error=None):
        now = time.time()
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT * FROM projects WHERE project=? AND owner=?', (job['project'], job['id'])).fetchone()
            if row is None:
                return
            next_status = 'queued' if row['wanted'] != job['revision'] or row['requested_tools'] != row['running_tools'] else status
            self.db.execute('UPDATE projects SET status=?,phase=NULL,owner=NULL,running=NULL,lease=NULL,built=?,updated=?,error=? WHERE project=? AND owner=?',
                            (next_status, job['revision'] if status == 'succeeded' else row['built'], now, error, job['project'], job['id']))
            self.db.execute('UPDATE runs SET status=?,finished=?,error=? WHERE id=?', (status, now, error, job['id']))
            if status == 'succeeded':
                for tool in job.get('tools', ['graphify', 'archify']):
                    column = {'graphify': 'built_graphify', 'archify': 'built_archify'}[tool]
                    self.db.execute(f'UPDATE projects SET {column}=? WHERE project=?', (job['revision'], job['project']))

    def run_one(self):
        job = self.claim()
        if not job:
            return None
        try:
            if self.builder:
                self.builder(job, self)
            else:
                from backend.maps.map_refresh_pipeline import build_maps
                build_maps(job, self)
            self.finish(job, 'succeeded')
        except Exception as exc:
            LOGGER.exception('Projektová aktualizace map selhala.')
            safe = str(exc)[:500] if isinstance(exc, ValueError) else 'Aktualizace selhala; poslední funkční mapy zůstaly zachovány.'
            self.finish(job, 'failed', safe)
        return job

    def retry(self, project, tool=None):
        if tool not in (None, 'graphify', 'archify'):
            raise ValueError('Neplatný nástroj mapy.')
        if not self.enabled():
            raise ValueError('Automatické aktualizace nejsou zapnuté.')
        root = main_project_root(self.service, project)
        revision = git(root, 'rev-parse', 'refs/heads/main', timeout=3)
        self.observe(project, root, revision)
        with self.lock, self.db:
            self.db.execute("UPDATE projects SET wanted=?,requested_tools=?,status=CASE WHEN owner IS NULL THEN 'queued' ELSE status END,error=NULL WHERE project=?", (revision, json.dumps([tool] if tool else ['graphify', 'archify']), project))
        return self.status(project)

    def settings(self, project, tool, automatic):
        if tool not in ('graphify', 'archify') or type(automatic) is not bool:
            raise ValueError('Neplatné nastavení aktualizace mapy.')
        root = main_project_root(self.service, project)
        revision = git(root, 'rev-parse', 'refs/heads/main', timeout=3)
        self.observe(project, root, revision, baseline=True)
        column = {'graphify': 'auto_graphify', 'archify': 'auto_archify'}[tool]
        with self.lock, self.db:
            self.db.execute(f'UPDATE projects SET {column}=? WHERE project=?', (int(automatic), project))
        return self.status(project)

    def status(self, project):
        self.service.project_hub.settings(project)
        with self.lock:
            row = self.db.execute('SELECT * FROM projects WHERE project=?', (project,)).fetchone()
            runs = [dict(r) for r in self.db.execute('SELECT id,revision,status,started,finished,error FROM runs WHERE project=? ORDER BY started DESC LIMIT 5', (project,))]
            return {'project': project, 'enabled': self.enabled(), 'status': row['status'] if row else 'unavailable',
                    'sourceRoot': row['root'] if row else None, 'observedRevision': row['observed'] if row else None,
                    'sourceRevision': row['built'] if row else None, 'phase': row['phase'] if row else None,
                    'automatic': {tool: bool(row['auto_' + tool]) if row else False for tool in ('graphify', 'archify')},
                    'versions': {tool: row['built_' + tool] if row else None for tool in ('graphify', 'archify')},
                    'error': row['error'] if row else None, 'runs': runs,
                    'trigger': 'refs/heads/main', 'agent': 'claude-code/sonnet', 'maxSeconds': 600, 'maxTurns': 10}

    def start(self):
        if not self.enabled() or self.thread and self.thread.is_alive():
            return
        self.stop.clear()
        self.thread = threading.Thread(target=self._loop, name='project-map-refresh', daemon=True)
        self.thread.start()

    def _loop(self):
        try:
            while not self.stop.is_set():
                try:
                    self.scan()
                    self.run_one()
                except (ValueError, OSError, sqlite3.Error):
                    pass
                self.stop.wait(5)
        finally:
            if self.closed:
                with self.lock:
                    self.db.close()

    def close(self):
        self.closed = True
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
        if not self.thread or not self.thread.is_alive():
            with self.lock:
                self.db.close()


def create_map_refresh_router(manager):
    router = APIRouter(prefix='/api/map-refresh', tags=['map-refresh'])

    @router.get('/status')
    def status(project: str = Query(min_length=1, max_length=64)):
        return manager.status(project)

    @router.post('/configure')
    def configure(payload: dict):
        if set(payload) != {'enabled'} or type(payload['enabled']) is not bool:
            raise ValueError('Očekáván pouze explicitní příznak enabled.')
        return manager.set_enabled(payload['enabled'])

    @router.post('/retry')
    def retry(project: str = Query(min_length=1, max_length=64), tool: str | None = Query(default=None)):
        return manager.retry(project, tool)

    @router.post('/settings')
    def settings(payload: dict):
        if set(payload) != {'project', 'tool', 'automatic'}:
            raise ValueError('Neplatný formát nastavení mapy.')
        return manager.settings(payload['project'], payload['tool'], payload['automatic'])

    return router
