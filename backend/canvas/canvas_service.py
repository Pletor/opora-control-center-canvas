import json
import os
import sqlite3
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from backend.canvas.graph import EMPTY, digest, encode, valid_id, validate_graph
from backend.canvas.migrate_to_project_folders import migrate
from backend.canvas.project_folder import ProjectFolder
from backend.editor.node.drawing_files import DrawingFileStore, parse_ids
from backend.editor.node.drawings import DrawingStore
from backend.editor.node.node_specs import EMPTY_FIELDS, NodeSpecStore, validate_payload
from backend.editor.node.node_text import NodeTextStore
from backend.editor.node.removals import RemovalService
from backend.integrations.gitio import git, github_url
from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.project_setup.project_hub import ProjectHub
from database.schema.project_schema import PROJECT_SCHEMA, REGISTRY_SCHEMA

GRAPH_FILE = "opora-canvas.json"


def now():
    return datetime.now(UTC).isoformat()


class CanvasService:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        migrate(self.root)  # stará centrální canvas.sqlite → registry + složky projektů (jednorázově)
        self.lock = threading.RLock()
        self.graph_lock = threading.RLock()
        self.git_lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=2)
        # registry.sqlite: jen seznam projektů, workspaces, jobs a archiv; vše ostatní má projekt ve své složce
        self.db = sqlite3.connect(self.root / "registry.sqlite", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(REGISTRY_SCHEMA)
        self._project_dbs = {}
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
        with self.graph_lock:
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
            with self.lock:
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
        with self.graph_lock:
            if self.view(pid, payload["workspace"])["readOnly"]:
                raise ValueError("Main je pouze pro čtení.")
            with self.lock:
                return self.drawing_files.put(pid, payload["file"])

    def drawing_file_list(self, pid, wid, ids):
        wanted = parse_ids(ids)
        with self.graph_lock:
            if self.view(pid, wid)["readOnly"]:
                return {"files": []}
            with self.lock:
                return {"files": self.drawing_files.get(pid, wanted)}

    def node_spec(self, pid, wid, node_id, payload=None, history=False):
        if payload is not None:
            validate_payload(payload)
        with self.graph_lock:
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
            with self.lock:
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
        with self.lock:
            for db in self._project_dbs.values():
                db.close()
            self._project_dbs.clear()
        self.db.close()

    def folder(self, pid):
        return ProjectFolder(self.root, pid)

    def db_for(self, pid):
        """Databáze jednoho projektu: projects/<id>/project.sqlite. Schéma vznikne při prvním otevření."""
        if not isinstance(pid, str) or (pid != "draft" and not valid_id(pid)):
            raise ValueError("Neplatné ID projektu.")
        with self.lock:
            db = self._project_dbs.get(pid)
            if db is None:
                folder = self.folder(pid)
                if pid == "draft" and not folder.exists():
                    folder.create("Lokální návrh", "empty")
                folder.path.mkdir(parents=True, exist_ok=True)
                db = sqlite3.connect(folder.database, check_same_thread=False)
                db.row_factory = sqlite3.Row
                db.executescript(PROJECT_SCHEMA)
                if pid == "draft":
                    db.execute("INSERT OR IGNORE INTO drafts VALUES('draft',?)", (encode(EMPTY),))
                db.commit()
                self._project_dbs[pid] = db
            return db

    def project_ids(self):
        """draft + všechny neodpojené projekty z registru."""
        with self.lock:
            rows = self.db.execute(
                "SELECT id FROM projects WHERE id NOT IN (SELECT project_id FROM archived_projects) ORDER BY id"
            ).fetchall()
        return ["draft", *(r[0] for r in rows)]

    def row(self, table, key):
        if table not in ("projects", "workspaces") or not valid_id(key):
            raise ValueError("Neplatný identifikátor.")
        if table == "projects" and self.removals.archived(key):
            raise ValueError("Projekt byl odpojen z aplikace.")
        row = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (key,)).fetchone()
        if row is None:
            raise ValueError("Položka nebyla nalezena.")
        return dict(row)

    def bootstrap(self):
        with self.lock:
            return {
                "draft": self.project_hub.settings("draft")["project"],
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
        with self.lock:
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
        with self.lock:
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

    def view(self, pid, wid):
        with self.lock:
            if pid == "draft" and wid == "draft":
                graph = json.loads(
                    self.db_for("draft").execute("SELECT graph FROM drafts WHERE id='draft'").fetchone()[0]
                )
                return {
                    "graph": graph,
                    "digest": digest(graph),
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
                row = self.db_for(pid).execute("SELECT graph FROM drafts WHERE id=?", (pid,)).fetchone()
                if row is None:
                    raise ValueError("Projektový draft nebyl nalezen.")
                graph = json.loads(row[0])
                return {
                    "graph": graph,
                    "digest": digest(graph),
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
        graph = validate_graph(json.loads(raw)) if raw else json.loads(encode(EMPTY))
        return {
            "graph": graph,
            "digest": digest(graph),
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

    def save_graph(self, pid, wid, graph, expected_digest, *, allow_removal=False, undo=False):
        """Uloží graf plátna. Běžné uložení uzel ani vazbu vypustit nesmí: k tomu je náhled a
        potvrzení odstranění (`allow_removal`, jen z `/api/remove`, které maže i obsah karty).

        `undo` je krok zpět (Ctrl+Z): vrací starší snímek plátna, takže vznik uzlu, komentáře,
        oblasti nebo vazby musí jít vzít zpět. Mění jen přítomnost v grafu — text uzlu, zadání,
        deník, kresba, stav Desktop v3 i prostor agenta zůstávají nedotčené, takže krok vpřed
        vrátí kartu i s obsahem. Konzistenci snímku hlídá `validate_graph` úplně stejně jako
        u běžného uložení: vazba na chybějící uzel i potomek chybějícího sektoru jsou neplatný graf.
        """
        validate_graph(graph)
        with self.graph_lock:
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
            # Zaokrouhlujeme až při zápisu; čtení starého grafu nesmí změnit jeho digest.
            graph = {"nodes": [{**node, "x": round(node["x"]), "y": round(node["y"])}
                               for node in graph["nodes"]], "edges": graph["edges"]}
            if pid == "draft" or self.project_hub.source_info(self.row("projects", pid))["sourceKind"] != "git":
                with self.lock:
                    db = self.db_for(pid)
                    db.execute("UPDATE drafts SET graph=? WHERE id=?", (encode(graph), pid))
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
            with self.lock:
                project = self.row("projects", pid)
                if self.project_hub.source_info(project)["sourceKind"] != "git":
                    raise ValueError("Lokální a prázdné projekty nevytvářejí Git pracovní prostory.")
            base = git(project["repo"], "rev-parse", "HEAD")
            wid = uuid.uuid4().hex
            branch = "work/" + wid
            directory = self.folder(pid).worktrees / wid
            directory.parent.mkdir(parents=True, exist_ok=True)
            git(project["repo"], "worktree", "add", "-b", branch, str(directory), base, timeout=60)
            with self.lock:
                self.row("projects", pid)
                self.db.execute(
                    "INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)",
                    (wid, pid, str(directory), branch, node_id, actor, base),
                )
                self.db.commit()
                return self.row("workspaces", wid)

    def job(self, kind, action, pid=None):
        with self.lock, self.db:
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
            with self.lock:
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
        with self.lock:
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
