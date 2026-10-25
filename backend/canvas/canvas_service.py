import json
import os
import re
import sqlite3
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path

from backend.canvas.architecture_graph import (
    check_shape,
    compose,
    ids,
    missing_links,
    references,
    same_content,
    split,
    visible_content,
)
from backend.canvas.graph import EMPTY, digest, encode, valid_id, validate_graph
from backend.canvas.migrate_to_project_folders import migrate
from backend.canvas.project_architecture import (
    ARCHITECTURE_WID,
    ProjectArchitecture,
    blocked_message,
)
from backend.canvas.project_folder import ProjectFolder
from backend.canvas.read_cache import ReadCache
from backend.canvas.workspace_graph import (
    LEGACY_GRAPH_FILE,
    read_workspace_graph,
    write_workspace_graph,
)
from backend.canvas.workspace_graph_storage import authoritative_raw, save_authoritative
from backend.editor.node.drawing_files import DrawingFileStore, parse_ids
from backend.editor.node.drawings import DrawingStore
from backend.editor.node.node_specs import EMPTY_FIELDS, NodeSpecStore, validate_payload
from backend.editor.node.node_text import NodeTextStore
from backend.editor.node.removals import RemovalService
from backend.integrations.gitio import git, github_url
from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.project.worktrees.workspace_archive import archived_workspaces
from backend.project.worktrees.workspace_domain import require_domain
from backend.project_setup.project_hub import ProjectHub
from database.repositories.opora_context_bindings import install as install_context_bindings
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import REGISTRY_SCHEMA

# Vrstva kresby skici momentu storyboardu: sb/<nodeId>/<momentId>.
_SKETCH_LAYER = re.compile(r"sb/(?P<node>[A-Za-z0-9_-]{1,80})/(?P<moment>m-[0-9a-f]{8})")
# Verzovaný graf v cílovém repu se už jen čte (main = Git HEAD). Pracovní prostory mají graf v datech plátna.
GRAPH_FILE = LEGACY_GRAPH_FILE
# Zapisovatel počká na zámek SQLite (WAL checkpoint, jiný proces), místo aby hned spadl na „database is locked“.
BUSY_TIMEOUT_MS = 5000
# Volná čtecí spojení na projekt: nad tuto mez se vrácené spojení zavře. Spojení se půjčuje na blok
# `reading`, ne na vlákno, takže počet otevřených nezávisí na tom, kolik vláken threadpool vystřídal.
READER_POOL_SIZE = 8
# Po checkpointu se soubor -wal zkrátí nejvýš na tuto velikost; bez meze zůstával na špičce
# (velký obrázek kresby, dlouhý snímek) až do vypnutí serveru.
JOURNAL_SIZE_LIMIT = 16 * 1024 * 1024
# Složka worktree = prvních 8 znaků ID pracovního prostoru (celé ID zůstává v DB i ve větvi work/<id>).
WORKTREE_FOLDER_LENGTH = 8
WORKTREE_FOLDER_ATTEMPTS = 20


class ProjectNotFound(ValueError):
    """Projekt s tímto ID (přesně, včetně velikosti písmen) neexistuje: HTTP 404 a nic se nezaloží."""

    def __init__(self, pid=""):
        super().__init__("Projekt neexistuje.")
        self.project = pid


def open_sqlite(path, *, reader=False):
    """Spojení SQLite ve WAL: čtenáři nečekají na zapisovatele a vidí jen potvrzená data.

    Čtecí spojení je jen pro čtení (`query_only`) a v autocommit režimu; transakci snímku
    otevírá `CanvasService.reading`.
    """
    db = sqlite3.connect(path, check_same_thread=False, isolation_level=None if reader else "")
    try:
        db.row_factory = sqlite3.Row
        db.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        db.execute(f"PRAGMA journal_size_limit={JOURNAL_SIZE_LIMIT}")
        if reader:
            db.execute("PRAGMA query_only=1")
        else:
            db.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        db.close()
        raise
    return db


def now():
    return datetime.now(UTC).isoformat()


class CanvasService:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        migrate(self.root)  # stará centrální canvas.sqlite → registry + složky projektů (jednorázově)
        # Zámky po projektech (karta P2): pořadí vždy graph_lock_for(p) → lock_for(p) → registry_lock.
        # Zámky dvou různých projektů se do sebe nevnořují; registry_lock je list (pod ním žádný zámek projektu).
        self._locks_guard = threading.Lock()
        self._project_locks = {}
        self._graph_locks = {}
        self.registry_lock = threading.RLock()
        self.git_lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=2)
        # registry.sqlite: jen seznam projektů, workspaces, jobs a archiv; vše ostatní má projekt ve své složce
        self.db = open_sqlite(self.root / "registry.sqlite")
        self.db.executescript(REGISTRY_SCHEMA)
        install_context_bindings(self.db)
        self._project_dbs = {}
        # Rozpracované snímky vlákna ({pid: spojení}); volná čtecí spojení po projektech (pod _locks_guard)
        # a seznam všech otevřených čtecích spojení kvůli close().
        self._local = threading.local()
        self._idle_readers = {}
        self._readers = []
        # Projekty, jejichž složka na disku existuje přesně pod tímto ID (karta P3): jen pro ně
        # vznikne zámek, spojení nebo soubor. Neznámé ID (i jiná velikost písmen) = ProjectNotFound.
        self._known_projects = set()
        # Sondy PRAGMA data_version (karta P3): {pid: (uid, spojení, zámek)}; registr pod klíčem None.
        self._probes = {}
        self.read_cache = ReadCache()
        # Skici momentů storyboardu (factory.py nastaví po vzniku StoryboardService; bez cyklu importů).
        self.sketch_layers_provider = None
        self.sketch_stale_callback = None
        self.architecture = ProjectArchitecture(self)
        self.drawings = DrawingStore(self)
        self.drawing_files = DrawingFileStore(self)
        self.specs = NodeSpecStore(self)
        self.removals = RemovalService(self)
        self.db.execute(
            "UPDATE jobs SET status='interrupted',message='Proces skončil před dokončením.' WHERE status IN ('queued','running')"
        )
        self.db.commit()
        self.project_hub = ProjectHub(self)
        self.texts = NodeTextStore(self)
        self.workspace_sources = WorkspaceSources(self)

    def drawing(self, pid, wid, layer, payload=None):
        sketch = _SKETCH_LAYER.fullmatch(layer) if isinstance(layer, str) else None
        if not sketch and (not isinstance(layer, str) or len(layer) > 80 or (layer and not valid_id(layer))):
            raise ValueError("Neplatná vrstva kresby.")
        if payload is not None and set(payload) != {
            "project",
            "workspace",
            "layer",
            "expected_revision",
            "scene",
        }:
            raise ValueError("Neplatný formát uložení kresby.")
        with self.reading(pid) if payload is None else self.graph_lock_for(pid):
            view = self.view(pid, wid)
            if sketch:
                # Skica momentu storyboardu: uzel existuje a moment je ve storyboardu karty.
                if not any(node["id"] == sketch["node"] for node in view["graph"]["nodes"]) or (
                    self.sketch_layers_provider is None
                    or layer not in self.sketch_layers_provider(pid, wid, sketch["node"])
                ):
                    raise ValueError("Skica momentu neexistuje.")
            elif layer and not any(node["id"] == layer for node in view["graph"]["nodes"]):
                raise ValueError("Vrstva kresby v tomto pracovním prostoru neexistuje.")
            if view["readOnly"]:
                if payload is not None:
                    raise ValueError("Main je pouze pro čtení.")
                return {
                    "scene": {"elements": []},
                    "revision": 0,
                    "readOnly": True,
                    "available": False,
                    "source": "Import kresby z Git mainu zatím není podporovaný.",
                    "saved_at": None,
                }
            scope = (pid, wid, layer)
            with nullcontext() if payload is None else self.lock_for(pid):
                result = (
                    self.drawings.read(scope)
                    if payload is None
                    else self.drawings.save(
                        scope, payload["expected_revision"], payload["scene"], now()
                    )
                )
        if sketch and payload is not None and self.sketch_stale_callback is not None:
            self.sketch_stale_callback(pid, wid, sketch["node"], sketch["moment"])
        return {
            **result,
            "readOnly": False,
            "available": True,
            "source": "Lokální kresba v SQLite; není součástí Git commitů.",
        }

    def drawing_file(self, payload):
        """Nahraje obrázek kresby; stejné hlídání projektu a prostoru jako `drawing`."""
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "file"}:
            raise ValueError("Neplatný formát nahrání obrázku kresby.")
        pid = payload["project"]
        with self.graph_lock_for(pid):
            if self.view(pid, payload["workspace"])["readOnly"]:
                raise ValueError("Main je pouze pro čtení.")
            with self.lock_for(pid):
                return self.drawing_files.put(pid, payload["file"])

    def drawing_file_list(self, pid, wid, ids):
        wanted = parse_ids(ids)
        with self.reading(pid):
            if self.view(pid, wid)["readOnly"]:
                return {"files": []}
            return {"files": self.drawing_files.get(pid, wanted)}

    def node_spec(self, pid, wid, node_id, payload=None):
        if payload is not None:
            validate_payload(payload)
        # Čtení zadání jde snímkem bez zámků; zápis drží zámek grafu a dat projektu.
        with self.reading(pid) if payload is None else self.graph_lock_for(pid):
            view = self.view(pid, wid)
            if not valid_id(node_id) or not any(n["id"] == node_id for n in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            # Zadání uzlu architektury leží pod `architecture`, takže jde číst i psát i z mainu.
            scope_wid = self.document_workspace(pid, wid, node_id)
            if view["readOnly"] and scope_wid == wid:
                if payload is not None:
                    raise ValueError("Main je pouze pro čtení.")
                return {
                    "revision": 0,
                    "fields": dict(EMPTY_FIELDS),
                    "saved_at": None,
                    "readOnly": True,
                    "available": False,
                    "source": "Import zadání z Git mainu zatím není podporovaný.",
                }
            with nullcontext() if payload is None else self.lock_for(pid):
                scope = (pid, scope_wid, node_id)
                result = (
                    self.specs.read(scope)
                    if payload is None
                    else self.specs.save(scope, payload["expected_revision"], payload["fields"])
                )
            return {
                **result,
                "readOnly": False,
                "available": True,
                "source": "Lokální editorové zadání v SQLite; není součástí Git commitů.",
            }

    def close(self):
        self.pool.shutdown(wait=True)
        with self._locks_guard:
            for db in [*self._readers, *self._project_dbs.values(), *(probe[1] for probe in self._probes.values())]:
                db.close()
            self._readers.clear()
            self._idle_readers.clear()
            self._project_dbs.clear()
            self._probes.clear()
        with self.registry_lock:
            self.db.close()

    def project_exists(self, pid):
        """Má projekt složku přesně pod tímto ID? Velikost písmen se porovnává i na Windows, kde
        by `ABC` otevřelo složku `abc`: alias jinak napsaného ID tak nedostane druhý zámek ani DB."""
        if pid == "draft" or pid in self._known_projects:
            return True
        if not isinstance(pid, str) or not valid_id(pid):
            return False
        try:
            names = os.listdir(self.root / "projects")
        except OSError:
            return False
        folder = self.folder(pid)
        if pid not in names or not (folder.identity_file.is_file() or folder.database.is_file()):
            return False
        with self._locks_guard:
            self._known_projects.add(pid)
        return True

    def forget_project(self, pid):
        """Smazaný nebo odpojený projekt: zahodí jeho odvozená čtení z paměti (cache)."""
        self.read_cache.drop(pid)

    def _project_lock(self, locks, pid):
        if pid != "draft" and not valid_id(pid):
            raise ValueError("Neplatné ID projektu.")
        with self._locks_guard:
            lock = locks.get(pid)
        if lock is not None:
            return lock
        # Zámek jen pro existující projekt: mapa zámků neroste s každým ID z požadavku.
        if not self.project_exists(pid):
            raise ProjectNotFound(pid)
        with self._locks_guard:
            return locks.setdefault(pid, threading.RLock())

    def lock_for(self, pid):
        """Zámek dat jednoho projektu: zápisové spojení SQLite a jeho transakce."""
        return self._project_lock(self._project_locks, pid)

    def graph_lock_for(self, pid):
        """Zámek grafu jednoho projektu: čtení grafu → ověření → zápis jako jeden krok."""
        return self._project_lock(self._graph_locks, pid)

    def _scopes(self):
        scopes = getattr(self._local, "scopes", None)
        if scopes is None:
            scopes = self._local.scopes = {}
            self._local.tokens = {}
            self._local.views = {}
        return scopes

    def _probe(self, pid):
        """Sonda změn projektu (pid) nebo registru (None): vlastní spojení jen pro PRAGMA data_version."""
        with self._locks_guard:
            probe = self._probes.get(pid)
        if probe is not None:
            return probe
        path = self.root / "registry.sqlite" if pid is None else self.folder(pid).database
        created = (uuid.uuid4().hex, open_sqlite(path, reader=True), threading.Lock())
        with self._locks_guard:
            probe = self._probes.setdefault(pid, created)
        if probe is not created:
            created[1].close()
        return probe

    def _probe_token(self, pid):
        """Razítko potvrzených dat: data_version se změní po každém commitu jiného spojení
        (zápisové spojení tohoto procesu i jiný proces nad stejnými daty). Uid sondy dělá razítko
        jedinečné pro tento proces, takže ho nejde zaměnit po restartu."""
        parts = []
        for key in (pid, None):
            uid, db, lock = self._probe(key)
            with lock:
                parts += [uid, db.execute("PRAGMA data_version").fetchone()[0]]
        return tuple(parts)

    def data_token(self, pid):
        """Token dat projektu pro cache čtení (karta P3); None = výsledek necachovat.

        Platí jen uvnitř `reading(pid)`: snímek bloku odpovídá přesně tomuto tokenu (žádný commit
        mezi přečtením tokenu a začátkem snímku). Při zápisu (vlákno drží `lock_for`) je None:
        zápisové spojení vidí i nepotvrzené změny."""
        if self.lock_for(pid)._is_owned():
            return None
        self._scopes()
        return self._local.tokens.get(pid)

    def view_token(self, pid, wid):
        """Token pro výsledky odvozené z grafu a dat projektu. Graf Git projektu leží v souboru
        nebo v Gitu, token SQLite ho nekryje: tam None (necachovat)."""
        token = self.data_token(pid)
        if token is None or (pid == "draft" and wid == "draft"):
            return token
        return token if self.project_hub.source_info(pid)["sourceKind"] != "git" else None

    def reader(self, pid):
        """Půjčí čtecí spojení projektu (WAL: nečeká na zapisovatele, nevidí rozpracované).

        Volající ho vrací přes `release_reader`; `reading` to dělá sám. Spojení se otevírá mimo
        `_locks_guard` (ten zůstává list bez I/O).
        """
        self.db_for(pid)  # schéma a WAL zajistí zápisové spojení
        with self._locks_guard:
            idle = self._idle_readers.get(pid)
            if idle:
                return idle.pop()
        db = open_sqlite(self.folder(pid).database, reader=True)
        with self._locks_guard:
            self._readers.append(db)
        return db

    def release_reader(self, pid, db):
        """Vrátí půjčené čtecí spojení: ukončí jeho snímek a nechá ho volné, nebo nad mezí zavře."""
        try:
            if db.in_transaction:
                db.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # poškozené spojení se nevrací, jen zavře
        else:
            with self._locks_guard:
                idle = self._idle_readers.setdefault(pid, [])
                if db in self._readers and len(idle) < READER_POOL_SIZE:
                    idle.append(db)
                    return
        with self._locks_guard:
            if db in self._readers:
                self._readers.remove(db)
        db.close()

    @contextmanager
    def reading(self, pid):
        """Čtení projektu bez zámků nad jedním konzistentním snímkem SQLite.

        Uvnitř bloku vrací `db_for(pid)` čtecí spojení tohoto vlákna. Drží-li vlákno zámek dat
        projektu (čtení uvnitř zápisu), zůstává zápisové spojení, aby čtení vidělo vlastní změny.
        Vnořené bloky sdílejí snímek vnějšího.

        Na začátku bloku se přečte token dat (`data_token`): před i po otevření snímku. Shodují-li
        se, snímek je přesně ten stav a cache čtení ho smí použít i uložit; jinak se v bloku necachuje.
        """
        scopes = self._scopes()
        if pid in scopes or self.lock_for(pid)._is_owned():
            yield
            return
        db = self.reader(pid)
        try:
            before = self._probe_token(pid)
            db.execute("BEGIN")
            db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()  # otevře snímek hned
            token = before if self._probe_token(pid) == before else None
            scopes[pid] = db
            self._local.tokens[pid] = token
            self._local.views[pid] = {}
            yield
        finally:
            scopes.pop(pid, None)
            self._local.tokens.pop(pid, None)
            self._local.views.pop(pid, None)
            self.release_reader(pid, db)

    @contextmanager
    def steady_reads(self, pid):
        """Čtecí blok pod zámkem dat projektu: `view` se v něm spočítá jednou na pracovní prostor.

        Pod zámkem `view` necachuje (zápisové spojení vidí vlastní změny), takže čtení, které drží
        zámek a projde všechny karty, pouštělo Git a parsování grafu pro každou kartu znovu. Volající
        zámek drží (nikdo jiný nezapisuje) a v bloku sám nezapisuje. Vnořené bloky sdílejí vnější."""
        steady = self._local.__dict__.setdefault("steady", {})
        if pid in steady:
            yield
            return
        steady[pid] = {}
        try:
            yield
        finally:
            steady.pop(pid, None)

    def steady_value(self, pid, key, compute):
        """Uvnitř `steady_reads` spočítá celoprojektovou hodnotu jednou na blok (klíč = n-tice, aby se
        nepletl s pohledy pod `wid`); mimo blok pokaždé znovu. Odmítnutí (`ValueError`) se pamatuje jako
        výsledek: čtení přes všechny karty pak neověřuje týž přijatý graf či kontext pro každou kartu."""
        memo = getattr(self._local, "steady", {}).get(pid)
        if memo is None:
            return compute()
        if key not in memo:
            try:
                memo[key] = (True, compute())
            except ValueError as error:
                memo[key] = (False, error)
        ok, value = memo[key]
        if not ok:
            raise value.with_traceback(None)
        return value

    def folder(self, pid):
        return ProjectFolder(self.root, pid)

    def graph_file(self, pid, wid):
        """Graf Git pracovního prostoru v datech plátna (projects/<id>/canvas/workspaces/<wid>/graph.json)."""
        return self.folder(pid).workspace_graph(wid)

    def db_for(self, pid):
        """Databáze jednoho projektu: projects/<id>/project.sqlite. Schéma vznikne při prvním otevření."""
        if not isinstance(pid, str) or (pid != "draft" and not valid_id(pid)):
            raise ValueError("Neplatné ID projektu.")
        scoped = self._scopes().get(pid)
        if scoped is not None and not self.lock_for(pid)._is_owned():
            return scoped
        db = self._project_dbs.get(pid)
        if db is not None:
            return db
        with self.lock_for(pid):  # neexistující projekt skončí ProjectNotFound dřív, než vznikne soubor
            db = self._project_dbs.get(pid)
            if db is None:
                folder = self.folder(pid)
                if pid == "draft" and not folder.exists():
                    folder.create("Lokální návrh", "empty")
                folder.path.mkdir(parents=True, exist_ok=True)
                db = open_sqlite(folder.database)
                initialize_project_schema(db)
                if pid == "draft":
                    db.execute("INSERT OR IGNORE INTO drafts VALUES('draft',?)", (encode(EMPTY),))
                db.commit()
                self._project_dbs[pid] = db
            return db

    def project_ids(self):
        """draft + všechny neodpojené projekty z registru."""
        with self.registry_lock:
            rows = self.db.execute(
                "SELECT id FROM projects WHERE id NOT IN (SELECT project_id FROM archived_projects) ORDER BY id"
            ).fetchall()
        return ["draft", *(r[0] for r in rows)]

    def row(self, table, key):
        if table not in ("projects", "workspaces") or not valid_id(key):
            raise ValueError("Neplatný identifikátor.")
        if table == "projects" and self.removals.archived(key):
            raise ValueError("Projekt byl odpojen z aplikace.")
        # Registr je jedno sdílené spojení: i krátké čtení drží registry_lock (list, pod ním nic dalšího).
        with self.registry_lock:
            row = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (key,)).fetchone()
        if row is None:
            raise ValueError("Položka nebyla nalezena.")
        return dict(row)

    def bootstrap(self):
        draft = self.project_hub.settings("draft")["project"]  # snímek draftu; registry_lock zůstává list
        with self.registry_lock:
            return {
                "draft": draft,
                "projects": [
                    {key: r[key] for key in ("id", "name", "url", "branch")}
                    | self.project_hub.source_info(dict(r))
                    for r in self.db.execute(
                        "SELECT id,name,repo,url,branch FROM projects WHERE id NOT IN (SELECT project_id FROM archived_projects) ORDER BY name"
                    )
                ],
                "jobs": [
                    dict(r)
                    for r in self.db.execute(
                        "SELECT * FROM jobs WHERE project_id IS NULL OR project_id NOT IN (SELECT project_id FROM archived_projects) ORDER BY updated_at DESC LIMIT 20"
                    )
                ],
                # Paměť agenta podle role: jen přepínač aplikace, bez síťového volání.
                # Skutečnou dostupnost říká teprve GET /api/memory/status.
                "memory": self.memory_bootstrap(),
            }

    def memory_bootstrap(self):
        """Stav paměti rolí pro bootstrap; `unknown` = zapnuto, ale server jsme se neptali."""
        service = getattr(self, "memory_service", None)
        if service is None:
            return {"enabled": False, "status": "disabled"}
        try:
            return service.bootstrap_status()
        except (ValueError, OSError, sqlite3.Error):
            return {"enabled": False, "status": "disabled"}

    def register_repository(self, pid, name, repo, url, branch):
        with self.registry_lock:
            if not valid_id(pid):
                raise ValueError("Neplatné ID projektu.")
            self.db.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?)", (pid, name, str(repo), url, branch)
            )
            self.db.commit()
            folder = self.folder(pid)
            if not folder.exists():
                folder.create(name or pid, "git", url or "", branch=branch or "")
            return self.row("projects", pid)

    def workspaces(self, pid):
        with self.registry_lock:
            return [
                dict(r)
                for r in self.db.execute(
                    "SELECT * FROM workspaces WHERE project_id=? AND id NOT IN (SELECT id FROM archived_workspaces)"
                    " ORDER BY id",
                    (pid,),
                )
            ]

    def location(self, pid, wid):
        project = self.row("projects", pid)
        if self.project_hub.source_info(project)["sourceKind"] != "git":
            raise ValueError("Lokální a prázdné projekty používají pouze pracovní prostor draft.")
        if wid == "main":
            return Path(project["repo"]), project
        workspace = self.row("workspaces", wid)
        if workspace["project_id"] != pid:
            raise ValueError("Pracovní prostor patří jinému projektu.")
        return Path(workspace["directory"]), project

    def _parsed_graph(self, pid, wid, raw, token=None, check=None):
        """(graph, digest) ze surového textu grafu přes cache: stejný token nebo stejný text = bez
        parsování a hashování. Graf je sdílený mezi požadavky, jen ke čtení (karta P3)."""
        key = ("graph", pid, wid)
        hit = self.read_cache.get(key, token)
        if hit is None:
            raw = raw()
            _stamp, previous = self.read_cache.peek(key)
            if previous is not None and previous[0] == raw:
                hit = previous
            else:
                graph = json.loads(raw)
                graph = check(graph) if check else graph
                hit = (raw, graph, digest(graph))
            self.read_cache.put(key, token, hit)
        return hit[1], hit[2]

    def _draft_graph(self, pid):
        def raw():
            from backend.canvas.opora_context_graph_storage import draft_authoritative_raw
            authoritative = draft_authoritative_raw(self, pid)
            if authoritative is not None:
                return authoritative
            row = self.db_for(pid).execute("SELECT graph FROM drafts WHERE id=?", (pid,)).fetchone()
            if row is None:
                raise ValueError("Projektový draft nebyl nalezen.")
            return row[0]

        return self._parsed_graph(pid, "draft", raw, self.data_token(pid))

    def view(self, pid, wid):
        """Graf plátna a jeho zdroj. Uvnitř jednoho `reading` bloku se počítá jednou (snímek se
        nemění) a vrací se mělká kopie; graf je sdílený, jen ke čtení."""
        with self.reading(pid):
            steady = getattr(self._local, "steady", {}).get(pid)
            memo = steady if steady is not None else None if self.lock_for(pid)._is_owned() else self._local.views.get(pid)
            if memo is not None and wid in memo:
                return dict(memo[wid])
            result = self._view(pid, wid)
            if memo is not None:
                memo[wid] = result
            return dict(result)

    def _view(self, pid, wid):
        # Čtení grafu jde přes snímek (WAL); uvnitř zápisu zůstává zápisové spojení s vlastními změnami.
        with self.reading(pid):
            architecture = self.architecture.read(pid)
            if pid == "draft" and wid == "draft":
                graph, graph_digest = self._draft_graph("draft")
                return self._composed_view(pid, wid, architecture, graph, graph_digest, False, {
                    "readOnly": False,
                    "source": "Lokální návrh, není schválený main",
                    "sha": None,
                    "branch": None,
                    "dirty": False,
                    "graphStatus": "present",
                    "workspaces": [],
                })
            project = self.row("projects", pid)
            source = self.project_hub.source_info(project)
            if source["sourceKind"] != "git":
                if wid != "draft":
                    raise ValueError("Lokální a prázdné projekty používají pouze pracovní prostor draft.")
                graph, graph_digest = self._draft_graph(pid)
                return self._composed_view(pid, wid, architecture, graph, graph_digest, False, {
                    "readOnly": False,
                    "source": "Lokální graf projektu v SQLite; zdrojová složka nebyla načtena.",
                    "sha": None,
                    "branch": None,
                    "dirty": False,
                    "graphStatus": "present",
                    "workspaces": [],
                })
            location, _project = self.location(pid, wid)
        # Pomalý Git nesmí držet zámek registru ani blokovat první načtení plátna.
        sha = git(location, "rev-parse", "HEAD")
        branch = git(location, "branch", "--show-current")
        dirty = bool(git(location, "status", "--porcelain"))
        raw, origin = self._git_content_raw(pid, wid, location, sha)
        # Soubor a Git nekryje token dat: graf se znovu neparsuje jen při stejném surovém textu.
        graph, graph_digest = self._parsed_graph(pid, wid, lambda: raw or encode(EMPTY), check=check_shape)
        return self._composed_view(pid, wid, architecture, graph, graph_digest, origin in ("git", "legacy"), {
            "readOnly": wid == "main",
            "source": "Git HEAD:" + GRAPH_FILE
            if wid == "main"
            else "Převzatý " + GRAPH_FILE + " z pracovního prostoru; první uložení ho převezme do dat plátna"
            if origin == "legacy"
            else "Graf pracovního prostoru v datech plátna",
            "sha": sha,
            "branch": branch,
            "dirty": dirty,
            "graphStatus": "present" if raw else "missing",
            "workspaces": self.workspaces(pid),
        })

    def _git_content_raw(self, pid, wid, location, sha=None):
        """(surový obsah, původ) Git prostoru: main = HEAD:opora-canvas.json, worktree = data plátna."""
        if wid == "main":
            return git(location, "show", (sha or "HEAD") + ":" + GRAPH_FILE, optional=True), "git"
        authoritative = authoritative_raw(self, pid, wid)
        if authoritative is not None:
            return authoritative, "sqlite"
        return read_workspace_graph(self.graph_file(pid, wid), location)

    def _composed_view(self, pid, wid, architecture, content, content_digest, legacy, fields):
        """Pohled = architektura ∪ obsah prostoru (docs/domeny-a-worktree.md §4); digest ze složeného grafu.

        Složení a jeho validace se drží v cache podle digestu architektury a obsahu."""
        key = ("composed", pid, wid)
        stamp = (architecture["digest"], architecture["raw"][2], content_digest, legacy)
        hit = self.read_cache.get(key, stamp)
        if hit is None:
            graph, conflicts = compose(architecture["graph"], architecture["removed"], content, legacy=legacy)
            # Graf z Gitu a souboru se ověřoval vždy; lokální graf z SQLite jen tehdy, když ho skládáme
            # s architekturou (dřív se nečetl s validací a starý projekt se nesmí přestat otevírat).
            if fields["sha"] is not None or architecture["graph"]["nodes"]:
                validate_graph(graph)
            hit = self.read_cache.put(key, stamp, {"graph": graph, "digest": digest(graph), "conflicts": conflicts})
        return {
            "graph": hit["graph"],
            "digest": hit["digest"],
            **fields,
            "architectureEditable": True,
            "architectureRevision": architecture["revision"],
            "conflicts": hit["conflicts"],
            "observedAt": now(),
        }

    def workspace_content(self, pid, wid):
        """(obsah prostoru bez architektury, legacy) přímo ze zdroje, bez skládání a bez Git stavu."""
        with self.reading(pid):
            if pid == "draft" or self.project_hub.source_info(self.row("projects", pid))["sourceKind"] != "git":
                if wid != "draft":
                    raise ValueError("Lokální a prázdné projekty používají pouze pracovní prostor draft.")
                return self._draft_graph(pid)[0], False
            location, _project = self.location(pid, wid)
        raw, origin = self._git_content_raw(pid, wid, location)
        return check_shape(json.loads(raw)) if raw else EMPTY, origin in ("git", "legacy")

    def architecture_references(self, pid, removed, *, skip=None, hidden=()):
        """Prostory, jejichž obsah nebo `workspaces.node_id` odkazuje na odebírané uzly architektury.

        [{workspace, label, reason}]; `skip` = prostor, jehož nový obsah ověřuje volající sám."""
        removed = set(removed)
        if not removed:
            return []
        if pid == "draft" or self.project_hub.source_info(self.row("projects", pid))["sourceKind"] != "git":
            spaces = [("draft", "draft")]
            rows = []
        else:
            rows = self.workspaces(pid)
            spaces = [("main", "main")] + [(row["id"], row["branch"] or row["id"]) for row in rows]
        hits = []
        for wid, label in spaces:
            if wid == skip:
                continue
            try:
                content, _legacy = self.workspace_content(pid, wid)
                referenced = references(content, removed, hidden)
            except (ValueError, OSError, subprocess.SubprocessError):
                hits.append({"workspace": wid, "label": label, "reason": "obsah nejde ověřit"})
                continue
            if referenced:
                hits.append({"workspace": wid, "label": label, "reason": "obsah"})
        hits += [{"workspace": row["id"], "label": row["branch"] or row["id"], "reason": "worktree domény"}
                 for row in rows if row["node_id"] in removed]
        return hits

    def archived_references(self, pid, removed):
        """Worktree ze skladiště, které patřily odebíraným uzlům: jen informace, odebrání neblokují."""
        removed = set(removed)
        if not removed or pid == "draft":
            return []
        return [{"workspace": item["id"], "label": item["branch"] or item["id"], "reason": "worktree ve skladišti"}
                for item in archived_workspaces(self, pid) if item["nodeId"] in removed]

    def document_workspace(self, pid, wid, node_id):
        """Prostor, pod kterým leží zadání a text uzlu: uzel architektury → `architecture`, jinak `wid`."""
        return ARCHITECTURE_WID if node_id in self.architecture.node_ids(pid) else wid

    def _nearest_sector(self, by_id, node):
        cursor = node.get("parentId")
        while cursor is not None:
            candidate = by_id.get(cursor)
            if candidate is None:
                return None
            if candidate["kind"] == "sector":
                return candidate
            cursor = candidate["parentId"]
        return None

    def _verify_source_refs(self, pid, wid, old_graph, new_graph):
        """Ověří rozsah všech existujících vazeb a disk jen pro změněné cesty."""
        old_by_id = {n["id"]: n for n in old_graph["nodes"]}
        new_by_id = {n["id"]: n for n in new_graph["nodes"]}
        root = None
        root_loaded = False

        def get_root():
            nonlocal root, root_loaded
            if not root_loaded:
                root = self.workspace_sources.root(pid, wid)
                root_loaded = True
            if root is None:
                raise ValueError("Projekt nemá připojenou zdrojovou složku.")
            return root

        for node in new_graph["nodes"]:
            ref = node.get("sourceRef")
            if not ref:
                continue

            if ref["origin"] == "existing":
                # Staré odkazy nesmí blokovat nesouvisející přesun po pozdějším
                # smazání souboru, jejich logický rozsah ale kontrolujeme vždy.
                old = old_by_id.get(node["id"])
                if old is None or old.get("sourceRef") != ref:
                    source_root = get_root()
                    try:
                        target = self.workspace_sources.target(source_root, ref["path"])
                    except (ValueError, OSError):
                        raise ValueError("Zdroj neodpovídá skutečnému souboru nebo složce.")
                    valid_kind = target.is_dir() if ref["kind"] == "directory" else target.is_file()
                    if not valid_kind:
                        raise ValueError("Zdroj neodpovídá skutečnému souboru nebo složce.")

            if node["kind"] != "node":
                continue
            sector = self._nearest_sector(new_by_id, node)
            sector_ref = sector.get("sourceRef") if sector else None
            # A conceptual sector groups work across repository directories. Its cards
            # carry project-relative paths; a bound sector still enforces its subtree.
            if sector is not None and not sector_ref:
                continue
            if ref["origin"] == "existing" and (not sector_ref or sector_ref["origin"] != "existing"):
                raise ValueError("Uzel s existujícím zdrojem vyžaduje existující zdroj sektoru.")
            if ref["origin"] == "planned" and not ref["path"]:
                continue
            if not sector_ref:
                raise ValueError("Navržený zdroj uzlu vyžaduje určenou cestu sektoru.")
            sector_path = sector_ref["path"]
            if ref["origin"] == "planned" and sector_ref["origin"] == "planned" and not sector_path:
                raise ValueError("Navržený zdroj uzlu nemůže vycházet z neurčené cesty sektoru.")
            own_path = ref["path"]
            within = own_path.startswith(sector_path + "/") if sector_path else bool(own_path)
            if not within:
                raise ValueError("Uzel odkazuje mimo svůj sektor.")

    def save_graph(self, pid, wid, graph, expected_digest, *, allow_removal=False, undo=False, _commit=True, actor="system"):
        """Uloží graf plátna. Běžné uložení uzel ani vazbu vypustit nesmí: k tomu je náhled a
        potvrzení odstranění (`allow_removal`, jen z `/api/remove`, které maže i obsah karty).

        `undo` je krok zpět (Ctrl+Z): vrací starší snímek plátna, takže vznik uzlu, komentáře,
        oblasti nebo vazby musí jít vzít zpět. Mění jen přítomnost v grafu — text uzlu, zadání,
        deník, kresba, stav Desktop v3 i prostor agenta zůstávají nedotčené, takže krok vpřed
        vrátí kartu i s obsahem. Konzistenci snímku hlídá `validate_graph` úplně stejně jako
        u běžného uložení: vazba na chybějící uzel i potomek chybějícího sektoru jsou neplatný graf.
        """
        validate_graph(graph)
        with self.graph_lock_for(pid):
            current = self.view(pid, wid)
            if current["digest"] != expected_digest:
                raise ValueError("Plátno se změnilo v jiném okně. Obnovte ho.")
            from backend.canvas.card_dag import check_save
            check_save(current["graph"], graph)  # 409 CardCycleError: `next` edges stay a DAG
            architecture = self.architecture.read(pid)
            arch_nodes, arch_edges = ids(architecture["graph"])
            if undo:
                # Krok zpět i obnova verze vrací jen obsah; architektura zůstává současná (§4).
                graph = self._content_only(architecture, graph)
            if not allow_removal and not undo:
                for collection in ("nodes", "edges"):
                    old_ids = {item["id"] for item in current["graph"][collection]}
                    new_ids = {item["id"] for item in graph[collection]}
                    if old_ids - new_ids:
                        raise ValueError("Mazání vyžaduje náhled a potvrzení odstranění.")
            self._verify_source_refs(pid, wid, current["graph"], graph)
            if actor not in ("human", "system"):
                # Brána, kontroly a vazby mezi sektory mění jen člověk (upgrade-opora #30).
                from backend.canvas.activity_log import HumanRequired
                from backend.canvas.protected_fields import protected_changes
                changes = protected_changes(current["graph"], graph)
                if changes:
                    raise HumanRequired(actor, "Tato pole mění jen člověk v UI: " + ", ".join(changes[:10]))
            # Zaokrouhlujeme až při zápisu; čtení starého grafu nesmí změnit jeho digest.
            graph = {"nodes": [{**node, "x": round(node["x"]), "y": round(node["y"])}
                               for node in graph["nodes"]], "edges": graph["edges"]}
            # Uzly se `site` a jejich předkové patří architektuře projektu, zbytek obsahu prostoru.
            new_arch, new_content = split(graph)
            new_arch_nodes, new_arch_edges = ids(new_arch)
            if current["readOnly"]:
                old_content = {"nodes": [n for n in current["graph"]["nodes"] if n["id"] not in arch_nodes],
                               "edges": [e for e in current["graph"]["edges"] if e["id"] not in arch_edges]}
                if not same_content(old_content, new_content, new_arch_nodes | new_arch_edges):
                    raise ValueError("Čistý main je pouze pro čtení. Vytvořte pracovní prostor; "
                                     "architekturu (domény a stránky) lze měnit i tady.")
            arch_changed = digest(new_arch) != architecture["digest"]
            if arch_changed:
                validate_graph(new_arch)
                hits = self.architecture_references(pid, arch_nodes - new_arch_nodes, skip=wid, hidden=new_arch_nodes)
                if hits:
                    raise ValueError(blocked_message(hits))
            kept = ids(new_content)
            if pid == "draft" or self.project_hub.source_info(self.row("projects", pid))["sourceKind"] != "git":
                from backend.canvas.opora_context_graph_storage import save_sql_draft
                if save_sql_draft(self, pid, wid, new_content, new_arch, architecture["revision"],
                                  arch_changed, actor, kept, commit=_commit):
                    return self.view(pid, wid)
                with self.lock_for(pid):
                    db = self.db_for(pid)
                    if not _commit and not db.in_transaction:
                        raise RuntimeError("Transakční zápis grafu vyžaduje otevřenou transakci.")
                    try:
                        if arch_changed:
                            self.architecture.write(db, pid, new_arch, architecture["revision"], actor, wid, kept)
                        db.execute("UPDATE drafts SET graph=? WHERE id=?", (encode(new_content), pid))
                        if _commit:
                            db.commit()
                    except Exception:
                        if _commit:
                            db.rollback()
                        raise
            else:
                # Cílové repo zůstává čisté: graf jde do dat plátna, starý soubor ve worktree se nepíše.
                self.location(pid, wid)
                if not current["readOnly"] and save_authoritative(
                    self, pid, wid, new_content, new_arch, architecture["revision"],
                    arch_changed, actor, kept, commit=_commit,
                ):
                    return self.view(pid, wid)
                if arch_changed:
                    # Architektura před obsahem: selže-li pak zápis souboru, kopie se při skládání skryjí.
                    with self.lock_for(pid):
                        db = self.db_for(pid)
                        try:
                            self.architecture.write(db, pid, new_arch, architecture["revision"], actor, wid, kept)
                            if _commit:
                                db.commit()
                        except Exception:
                            if _commit:
                                db.rollback()
                            raise
                if not current["readOnly"]:
                    write_workspace_graph(self.graph_file(pid, wid), encode(new_content))
            return self.view(pid, wid)

    def save_positions(self, pid, wid, positions, expected_digest, *, actor="system"):
        """Posun karet bez celého grafu (`docs/navrhy/2026-10-14-vykon-platna.md`, oprava 8).

        `positions` = [{id, x, y}] uzlů, které už v pohledu jsou; neznámé ID, duplicita nebo jiné
        pole uložení odmítne. Graf se složí z uloženého pohledu a jde přes `save_graph`, takže
        rozdělení na architekturu a obsah i pravidlo čistého mainu (jen architektura) platí beze
        změny. Vrací pohled bez grafu a zaokrouhlené pozice, jak je server uložil."""
        import math

        if not isinstance(positions, list) or not 0 < len(positions) <= 2000:
            raise ValueError("Pozice jsou neprázdný seznam nejvýše 2000 uzlů.")
        moved = {}
        for item in positions:
            if (not isinstance(item, dict) or set(item) != {"id", "x", "y"} or not valid_id(item["id"])
                    or any(type(item[k]) not in (int, float) or not math.isfinite(item[k]) for k in ("x", "y"))):
                raise ValueError("Pozice uzlu je {id, x, y} s konečnými čísly.")
            if item["id"] in moved:
                raise ValueError("Pozice uzlu se v jednom zápisu opakuje.")
            moved[item["id"]] = (round(item["x"]), round(item["y"]))
        with self.graph_lock_for(pid):
            current = self.view(pid, wid)
            if current["digest"] != expected_digest:
                raise ValueError("Plátno se změnilo v jiném okně. Obnovte ho.")
            unknown = set(moved) - {node["id"] for node in current["graph"]["nodes"]}
            if unknown:
                raise ValueError("Pozice míří na neexistující uzel: " + ", ".join(sorted(unknown)[:5]))
            graph = {"nodes": [{**node, "x": moved[node["id"]][0], "y": moved[node["id"]][1]} if node["id"] in moved
                               else node for node in current["graph"]["nodes"]],
                     "edges": current["graph"]["edges"]}
            saved = self.save_graph(pid, wid, graph, expected_digest, actor=actor)
        return {**{key: value for key, value in saved.items() if key != "graph"},
                "positions": [{"id": key, "x": x, "y": y} for key, (x, y) in moved.items()]}

    def _content_only(self, architecture, graph):
        """Složený graf ze současné architektury a obsahu staršího snímku (krok zpět, obnova verze)."""
        _snapshot_architecture, snapshot_content = split(graph)
        content, _conflicts = visible_content(architecture["graph"], architecture["removed"], snapshot_content, legacy=False)
        missing = missing_links(architecture["graph"], content)
        if missing:
            raise ValueError("Obsah odkazuje na doménu nebo stránku, která už v architektuře není ("
                             + ", ".join(map(str, missing[:5]))
                             + "). Nejdřív obnovte revizi architektury.")
        composed = {"nodes": [*architecture["graph"]["nodes"], *content["nodes"]],
                    "edges": [*architecture["graph"]["edges"], *content["edges"]]}
        return validate_graph(composed)

    def create_workspace(self, pid, node_id, actor):
        if (
            not valid_id(node_id)
            or not isinstance(actor, str)
            or not actor.strip()
            or len(actor) > 120
        ):
            raise ValueError("Vyplňte uzel a označení vlastníka pracovního prostoru.")
        require_domain(self, pid, node_id)
        return self._add_worktree(pid, node_id, actor)

    def _add_worktree(self, pid, node_id, actor):
        """Git worktree z HEAD mainu + řádek `workspaces`; doménu ověřuje `create_workspace`."""
        with self.git_lock:
            with self.registry_lock:
                project = self.row("projects", pid)
                if self.project_hub.source_info(project)["sourceKind"] != "git":
                    raise ValueError("Lokální a prázdné projekty nevytvářejí Git pracovní prostory.")
            base = git(project["repo"], "rev-parse", "HEAD")
            wid, directory = self._new_worktree_folder(pid)
            branch = "work/" + wid
            git(project["repo"], "worktree", "add", "-b", branch, str(directory), base, timeout=60)
            with self.registry_lock:
                self.row("projects", pid)
                self.db.execute(
                    "INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)",
                    (wid, pid, str(directory), branch, node_id, actor, base),
                )
                self.db.commit()
                return self.row("workspaces", wid)

    def _new_worktree_folder(self, pid):
        """(wid, složka) nového worktree. Složka nese jen prvních 8 znaků ID: cesta v datech plus
        hluboké soubory repozitáře se tak vejdou pod limit Windows. Obsazenou složku nikdy nesdílí."""
        root = self.folder(pid).worktrees
        root.mkdir(parents=True, exist_ok=True)
        for _ in range(WORKTREE_FOLDER_ATTEMPTS):
            wid = uuid.uuid4().hex
            directory = root / wid[:WORKTREE_FOLDER_LENGTH]
            if not directory.exists():
                return wid, directory
        raise ValueError("Nepodařilo se najít volnou složku pro pracovní prostor; zkuste to znovu.")

    def job(self, kind, action, pid=None):
        with self.registry_lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if pid is not None and self.removals.archived(pid):
                raise ValueError("Projekt byl odpojen z aplikace.")
            jid = uuid.uuid4().hex
            self.db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,?)",
                (jid, kind, "queued", "Čeká na provedení.", pid, now()),
            )
            self.db.commit()

        def update(status, message, project=pid):
            with self.registry_lock:
                self.db.execute(
                    "UPDATE jobs SET status=?,message=?,project_id=?,updated_at=? WHERE id=?",
                    (status, message, project, now(), jid),
                )
                self.db.commit()

        def worker():
            update("running", "Probíhá Git operace na pozadí.")
            try:
                result = action()
                update("complete", "Dokončeno a ověřeno.", result or pid)
            except (OSError, ValueError, subprocess.SubprocessError):
                update(
                    "failed",
                    "Operace selhala; ověřte přístup ke GitHubu, stav repozitáře a dostupnost sítě. Žádný push nebo merge nebyl proveden.",
                )

        self.pool.submit(worker)
        return {"jobId": jid}

    def connect(self, url, approved):
        github_url(url)
        if approved is not True:
            raise ValueError("Nejprve schvalte konkrétní GitHub zdroj.")
        pid = uuid.uuid4().hex
        repo = self.root / "projects" / pid / "main"

        def clone():
            repo.parent.mkdir(parents=True, exist_ok=True)
            git(None, "clone", "--no-recurse-submodules", "--", url, str(repo), timeout=180)
            branch = git(repo, "branch", "--show-current")
            if not branch:
                raise ValueError("Chybí výchozí větev.")
            git(repo, "rev-parse", "HEAD")
            self.register_repository(pid, url.rsplit("/", 1)[-1], str(repo), url, branch)
            return pid

        return self.job("clone", clone, pid)

    def sync(self, pid):
        with self.registry_lock:
            project = self.row("projects", pid)
            if self.project_hub.source_info(project)["sourceKind"] != "git":
                raise ValueError("Lokální a prázdné projekty nelze synchronizovat přes Git.")

        def synchronize():
            repo = project["repo"]
            if (
                git(repo, "remote", "get-url", "origin") != project["url"]
                or git(repo, "branch", "--show-current") != project["branch"]
                or git(repo, "status", "--porcelain")
            ):
                raise ValueError("Main není čistý nebo nesouhlasí upstream.")
            git(repo, "fetch", "origin", timeout=120)
            target = "refs/remotes/origin/" + project["branch"]
            git(repo, "merge", "--ff-only", target, timeout=30)
            if git(repo, "rev-parse", "HEAD") != git(repo, "rev-parse", target):
                raise ValueError("Revize nebyla synchronizována.")
            return pid

        return self.job("sync", synchronize, pid)
