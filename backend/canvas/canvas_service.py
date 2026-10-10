import json
import os
import sqlite3
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path

from backend.canvas.graph import EMPTY, digest, encode, valid_id, validate_graph
from backend.canvas.migrate_to_project_folders import migrate
from backend.canvas.project_folder import ProjectFolder
from backend.canvas.read_cache import ReadCache
from backend.editor.node.drawing_files import DrawingFileStore, parse_ids
from backend.editor.node.drawings import DrawingStore
from backend.editor.node.node_specs import EMPTY_FIELDS, NodeSpecStore, validate_payload
from backend.editor.node.node_text import NodeTextStore
from backend.editor.node.removals import RemovalService
from backend.integrations.gitio import git, github_url
from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.project_setup.project_hub import ProjectHub
from database.schema.project_schema import (
    PROJECT_SCHEMA,
    REGISTRY_SCHEMA,
    ensure_canvas_version_columns,
)

GRAPH_FILE = "opora-canvas.json"
# Zapisovatel počká na zámek SQLite (WAL checkpoint, jiný proces), místo aby hned spadl na „database is locked“.
BUSY_TIMEOUT_MS = 5000
# Volná čtecí spojení na projekt: nad tuto mez se vrácené spojení zavře. Spojení se půjčuje na blok
# `reading`, ne na vlákno, takže počet otevřených nezávisí na tom, kolik vláken threadpool vystřídal.
READER_POOL_SIZE = 8
# Po checkpointu se soubor -wal zkrátí nejvýš na tuto velikost; bez meze zůstával na špičce
# (velký obrázek kresby, dlouhý snímek) až do vypnutí serveru.
JOURNAL_SIZE_LIMIT = 16 * 1024 * 1024


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
        if not isinstance(layer, str) or len(layer) > 80 or (layer and not valid_id(layer)):
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
            if layer and not any(node["id"] == layer for node in view["graph"]["nodes"]):
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

    def node_spec(self, pid, wid, node_id, payload=None, history=False):
        if payload is not None:
            validate_payload(payload)
        # Čtení zadání jde snímkem bez zámků; zápis drží zámek grafu a dat projektu.
        with self.reading(pid) if payload is None else self.graph_lock_for(pid):
            view = self.view(pid, wid)
            if not valid_id(node_id) or not any(n["id"] == node_id for n in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            if view["readOnly"]:
                if payload is not None:
                    raise ValueError("Main je pouze pro čtení.")
                return {
                    **(
                        {"items": [], "has_more": False}
                        if history
                        else {"revision": 0, "fields": dict(EMPTY_FIELDS), "saved_at": None}
                    ),
                    "readOnly": True,
                    "available": False,
                    "source": "Import zadání z Git mainu zatím není podporovaný.",
                }
            with nullcontext() if payload is None else self.lock_for(pid):
                scope = (pid, wid, node_id)
                result = (
                    self.specs.history(scope)
                    if history
                    else self.specs.read(scope)
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

    def folder(self, pid):
        return ProjectFolder(self.root, pid)

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
                db.executescript(PROJECT_SCHEMA)
                ensure_canvas_version_columns(db)
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
                    "SELECT * FROM workspaces WHERE project_id=? ORDER BY id", (pid,)
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
            row = self.db_for(pid).execute("SELECT graph FROM drafts WHERE id=?", (pid,)).fetchone()
            if row is None:
                raise ValueError("Projektový draft nebyl nalezen.")
            return row[0]

        return self._parsed_graph(pid, "draft", raw, self.data_token(pid))

    def view(self, pid, wid):
        """Graf plátna a jeho zdroj. Uvnitř jednoho `reading` bloku se počítá jednou (snímek se
        nemění) a vrací se mělká kopie; graf je sdílený, jen ke čtení."""
        with self.reading(pid):
            memo = None if self.lock_for(pid)._is_owned() else self._local.views.get(pid)
            if memo is not None and wid in memo:
                return dict(memo[wid])
            result = self._view(pid, wid)
            if memo is not None:
                memo[wid] = result
            return dict(result)

    def _view(self, pid, wid):
        # Čtení grafu jde přes snímek (WAL); uvnitř zápisu zůstává zápisové spojení s vlastními změnami.
        with self.reading(pid):
            if pid == "draft" and wid == "draft":
                graph, graph_digest = self._draft_graph("draft")
                return {
                    "graph": graph,
                    "digest": graph_digest,
                    "readOnly": False,
                    "source": "Lokální návrh, není schválený main",
                    "sha": None,
                    "branch": None,
                    "dirty": False,
                    "graphStatus": "present",
                    "workspaces": [],
                    "observedAt": now(),
                }
            project = self.row("projects", pid)
            source = self.project_hub.source_info(project)
            if source["sourceKind"] != "git":
                if wid != "draft":
                    raise ValueError("Lokální a prázdné projekty používají pouze pracovní prostor draft.")
                graph, graph_digest = self._draft_graph(pid)
                return {
                    "graph": graph,
                    "digest": graph_digest,
                    "readOnly": False,
                    "source": "Lokální graf projektu v SQLite; zdrojová složka nebyla načtena.",
                    "sha": None,
                    "branch": None,
                    "dirty": False,
                    "graphStatus": "present",
                    "workspaces": [],
                    "observedAt": now(),
                }
            location, _project = self.location(pid, wid)
        # Pomalý Git nesmí držet zámek registru ani blokovat první načtení plátna.
        sha = git(location, "rev-parse", "HEAD")
        branch = git(location, "branch", "--show-current")
        dirty = bool(git(location, "status", "--porcelain"))
        if wid == "main":
            raw = git(location, "show", sha + ":" + GRAPH_FILE, optional=True)
        else:
            file = location / GRAPH_FILE
            if file.is_symlink():
                raise ValueError("Graf nesmí být symbolický odkaz.")
            if file.exists() and file.stat().st_size > 2000000:
                raise ValueError("Graf je příliš velký.")
            raw = file.read_text(encoding="utf-8") if file.exists() else None
        # Soubor a Git nekryje token dat: graf se znovu neparsuje jen při stejném surovém textu.
        graph, graph_digest = self._parsed_graph(pid, wid, lambda: raw or encode(EMPTY), check=validate_graph if raw else None)
        return {
            "graph": graph,
            "digest": graph_digest,
            "readOnly": wid == "main",
            "source": "Git HEAD:" + GRAPH_FILE
            if wid == "main"
            else "Pracovní soubor " + GRAPH_FILE,
            "sha": sha,
            "branch": branch,
            "dirty": dirty,
            "graphStatus": "present" if raw else "missing",
            "workspaces": self.workspaces(pid),
            "observedAt": now(),
        }

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
            if current["readOnly"]:
                raise ValueError("Čistý main je pouze pro čtení. Vytvořte pracovní prostor.")
            if current["digest"] != expected_digest:
                raise ValueError("Plátno se změnilo v jiném okně. Obnovte ho.")
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
            if pid == "draft" or self.project_hub.source_info(self.row("projects", pid))["sourceKind"] != "git":
                with self.lock_for(pid):
                    db = self.db_for(pid)
                    if not _commit and not db.in_transaction:
                        raise RuntimeError("Transakční zápis grafu vyžaduje otevřenou transakci.")
                    db.execute("UPDATE drafts SET graph=? WHERE id=?", (encode(graph), pid))
                    if _commit:
                        db.commit()
            else:
                location, _ = self.location(pid, wid)
                target = location / GRAPH_FILE
                temp = location / (".canvas-" + uuid.uuid4().hex + ".tmp")
                temp.write_text(encode(graph), encoding="utf-8")
                os.replace(temp, target)
            return self.view(pid, wid)

    def create_workspace(self, pid, node_id, actor):
        if (
            not valid_id(node_id)
            or not isinstance(actor, str)
            or not actor.strip()
            or len(actor) > 120
        ):
            raise ValueError("Vyplňte uzel a označení vlastníka pracovního prostoru.")
        with self.git_lock:
            with self.registry_lock:
                project = self.row("projects", pid)
                if self.project_hub.source_info(project)["sourceKind"] != "git":
                    raise ValueError("Lokální a prázdné projekty nevytvářejí Git pracovní prostory.")
            base = git(project["repo"], "rev-parse", "HEAD")
            wid = uuid.uuid4().hex
            branch = "work/" + wid
            directory = self.folder(pid).worktrees / wid
            directory.parent.mkdir(parents=True, exist_ok=True)
            git(project["repo"], "worktree", "add", "-b", branch, str(directory), base, timeout=60)
            with self.registry_lock:
                self.row("projects", pid)
                self.db.execute(
                    "INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)",
                    (wid, pid, str(directory), branch, node_id, actor, base),
                )
                self.db.commit()
                return self.row("workspaces", wid)

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
