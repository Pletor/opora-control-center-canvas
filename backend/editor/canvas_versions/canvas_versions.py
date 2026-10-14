"""Saved workspace checkpoints with full-content CAS and exception-atomic restore."""
import json
import re
import uuid
from datetime import UTC, datetime

from backend.canvas.graph import digest, encode

from .version_assets import capture_assets, file_rollback, unavailable_assets
from .version_content import (
    EXCLUDED,
    SCHEMA,
    content_digest,
    current_token,
    empty_data,
    read_records,
    with_later_stores,
)
from .version_metadata import changed_cards
from .version_restore import check_closed_records, preflight, write_content

MAX_VERSIONS = 200
# Retence (upgrade-opora #41): každá verze nese kopii assetů, smyčka „Uložit vše“ nesmí nafouknout DB.
MAX_STORED = 300
MAX_AUTHOR = 120
SAVE_KEYS = {"project", "workspace", "digest", "author"}
RESTORE_KEYS = SAVE_KEYS | {"versionId"}
VERSION_ID = re.compile(r"[0-9a-f]{32}")
BEFORE_RESTORE = " (před obnovením)"
READ_ONLY = "Main je pouze pro čtení. Přepněte do pracovního prostoru."
CHANGED = "Plátno nebo jeho obsah se změnilo v jiném okně. Obnovte ho."


def _now():
    return datetime.now(UTC).isoformat()


def _payload(payload, keys):
    if not isinstance(payload, dict) or set(payload) not in (keys, keys | {"expectedToken"}):
        raise ValueError("Verze očekává project, workspace, digest, author a případně expectedToken / versionId.")
    author = payload["author"]
    if not isinstance(author, str) or "\0" in author or not author.strip() or len(author) > MAX_AUTHOR:
        raise ValueError(f"Autor verze musí být text o 1 až {MAX_AUTHOR} znacích.")
    if "expectedToken" in payload and (not isinstance(payload["expectedToken"], str) or not payload["expectedToken"]):
        raise ValueError("Neplatný token pracovního prostoru.")
    return author.strip()


def _summary(row):
    snapshot = json.loads(row["snapshot"]) if row["snapshot"] else None
    return {"id": row["id"], "createdAt": row["created_at"], "author": row["author"],
            "actor": (snapshot or {}).get("saveMetadata", {}).get("actor", "unknown"),
            "changedCardCount": (snapshot or {}).get("saveMetadata", {}).get("changedCardCount"),
            "nodeCount": len(json.loads(row["graph"])["nodes"]),
            "coverage": "full" if snapshot else "legacy-partial", "unavailableAssets": unavailable_assets(snapshot)}


# Výpis verzí bez blobů (karta P1): sloupce graph/state/snapshot (~5 MB na verzi) se do Pythonu nečtou.
# Počet uzlů spočítá SQLite z grafu; typeof(snapshot) nečte obsah sloupce.
LIST_SQL = ("SELECT id, created_at, author, json_array_length(graph, '$.nodes') AS node_count,"
            " typeof(snapshot) = 'text' AS has_snapshot FROM canvas_versions"
            " WHERE project_id=? AND workspace_id=? ORDER BY created_at DESC,rowid DESC LIMIT ?")
# Metadata uvnitř snímku spočítá SQLite (json_extract / json_each) jen pro verze, které ještě nejsou
# v paměti. Řádek verze se po vložení nemění (id = uuid4), proto jeho metadata stačí přečíst jednou.
SNAPSHOT_SQL = ("SELECT id, CASE WHEN json_type(snapshot, '$.saveMetadata.actor') IS NULL THEN 'unknown'"
                " ELSE json_extract(snapshot, '$.saveMetadata.actor') END AS actor,"
                " json_extract(snapshot, '$.saveMetadata.changedCardCount') AS changed,"
                " (SELECT count(*) FROM json_each(snapshot, '$.assets.uploads')"
                " WHERE json_type(value, '$.data') = 'null')"
                " + (SELECT count(*) FROM json_each(snapshot, '$.assets.drawings')"
                " WHERE json_type(value, '$.file') = 'null') AS unavailable"
                " FROM canvas_versions WHERE project_id=? AND workspace_id=? AND id IN ({})")
# Je obsah už uložený? Jde přes index canvas_versions_content (database/schema/project_schema.py).
SAME_CONTENT_SQL = "SELECT 1 FROM canvas_versions WHERE project_id=? AND workspace_id=? AND content_digest=? LIMIT 1"
LEGACY = {"actor": "unknown", "changedCardCount": None, "coverage": "legacy-partial", "unavailableAssets": 0}


class CanvasVersions:
    def __init__(self, canvas, desktop_state=None):
        self.canvas, self._desktop_state = canvas, desktop_state
        # (project, workspace) -> {id verze: metadata ze snímku}; řádky verzí se nemění, proto
        # stačí atomické přiřazení slovníku (čte se i bez zámku projektu).
        self._snapshot_meta = {}

    def _summaries(self, db, project, workspace):
        rows = db.execute(LIST_SQL, (project, workspace, MAX_VERSIONS)).fetchall()
        known = self._snapshot_meta.get((project, workspace), {})
        meta = {row["id"]: known.get(row["id"], LEGACY) for row in rows}
        missing = [row["id"] for row in rows if row["has_snapshot"] and row["id"] not in known]
        if missing:
            query = SNAPSHOT_SQL.format(",".join("?" * len(missing)))
            for item in db.execute(query, (project, workspace, *missing)):
                meta[item["id"]] = {"actor": item["actor"], "changedCardCount": item["changed"],
                                    "coverage": "full", "unavailableAssets": item["unavailable"]}
        # Jen verze z aktuálního výpisu: smazané retencí z paměti zmizí.
        self._snapshot_meta[(project, workspace)] = meta
        return [{"id": row["id"], "createdAt": row["created_at"], "author": row["author"],
                 "actor": meta[row["id"]]["actor"], "changedCardCount": meta[row["id"]]["changedCardCount"],
                 "nodeCount": row["node_count"], "coverage": meta[row["id"]]["coverage"],
                 "unavailableAssets": meta[row["id"]]["unavailableAssets"]} for row in rows]

    def desktop_state(self):
        from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
        return self._desktop_state or getattr(self.canvas, "desktop_v3_state", None) or DesktopV3State(self.canvas)

    def _capture(self, db, project, workspace):
        view = self.canvas.view(project, workspace)
        stored = self.desktop_state().current(project, workspace)
        records = read_records(db, project, workspace)
        settings = self.canvas.project_hub.settings(project)
        snapshot = {"schema": SCHEMA, "records": records,
                    "assets": capture_assets(self.canvas, db, project, stored["state"], records),
                    "excluded": EXCLUDED, "projectGoal": {"goal": settings["settings"]["goal"], "revision": settings["revision"], "restore": False}}
        snapshot["integrity"] = digest(snapshot)
        return view, stored, snapshot

    def _dirty(self, db, project, workspace, view, stored, snapshot):
        from backend.editor.agent_memory.desktop_v3_state import default_state
        matching = db.execute(SAME_CONTENT_SQL, (project, workspace, content_digest(view["graph"], stored["state"], snapshot))).fetchone()
        if matching:
            return False
        any_version = db.execute("SELECT 1 FROM canvas_versions WHERE project_id=? AND workspace_id=? LIMIT 1", (project, workspace)).fetchone()
        return bool(any_version or view["graph"]["nodes"] or view["graph"]["edges"] or stored["state"] != default_state()
                    or any(row["data"] != empty_data(name) for name, rows in snapshot["records"].items() for row in rows))

    def _insert(self, db, project, workspace, author, graph, state, snapshot, actor="human"):
        previous = db.execute("SELECT graph,state,snapshot FROM canvas_versions WHERE project_id=? AND workspace_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                              (project, workspace)).fetchone()
        before = (json.loads(previous["graph"]), json.loads(previous["state"]),
                  json.loads(previous["snapshot"]) if previous["snapshot"] else None) if previous else None
        count = changed_cards(graph, state, snapshot, before)
        snapshot = {**snapshot, "saveMetadata": {"actor": actor, "changedCardCount": count}}
        snapshot["integrity"] = digest({key: value for key, value in snapshot.items() if key != "integrity"})
        version_id, timestamp = uuid.uuid4().hex, _now()
        db.execute("INSERT INTO canvas_versions(id,project_id,workspace_id,author,created_at,graph,state,graph_digest,state_digest,snapshot,content_digest)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?,?)", (version_id, project, workspace, author, timestamp, encode(graph), encode(state),
                                                     digest(graph), digest(state), encode(snapshot), content_digest(graph, state, snapshot)))
        db.execute("DELETE FROM canvas_versions WHERE project_id=? AND workspace_id=? AND id NOT IN ("
                   "SELECT id FROM canvas_versions WHERE project_id=? AND workspace_id=? ORDER BY created_at DESC,rowid DESC LIMIT ?)",
                   (project, workspace, project, workspace, MAX_STORED))
        return {"id": version_id, "createdAt": timestamp, "author": author, "nodeCount": len(graph["nodes"]),
                "actor": actor, "changedCardCount": count,
                "coverage": "full", "unavailableAssets": unavailable_assets(snapshot)}

    def list(self, project, workspace):
        # Bez zámků projektu (karta P2): jeden snímek WAL, takže stav, záznamy i verze jsou
        # konzistentní a zápis (lease, stav, nová verze) na výpis nečeká. Výsledek se drží
        # v cache podle tokenu dat (karta P3): polling beze změny nic nepřepočítává.
        with self.canvas.reading(project):
            return self._cached("canvas-versions", project, workspace, lambda db: {
                "versions": self._summaries(db, project, workspace), **self._head(db, project, workspace)})

    def head(self, project, workspace):
        """Jen `currentToken` a `dirty` (levný polling klienta); z výpisu v cache, pokud platí."""
        with self.canvas.reading(project):
            listed = self.canvas.read_cache.get(("canvas-versions", project, workspace), self.canvas.view_token(project, workspace))
            if listed is not None:
                return {"currentToken": listed["currentToken"], "dirty": listed["dirty"]}
            return self._cached("canvas-versions-head", project, workspace, lambda db: self._head(db, project, workspace))

    def _head(self, db, project, workspace):
        view, stored, snapshot = self._capture(db, project, workspace)
        return {"dirty": False if view["readOnly"] else self._dirty(db, project, workspace, view, stored, snapshot),
                "currentToken": current_token(view["graph"], stored, snapshot)}

    def _cached(self, kind, project, workspace, build):
        key = (kind, project, workspace)
        token = self.canvas.view_token(project, workspace)
        cached = self.canvas.read_cache.get(key, token)
        if cached is None:
            cached = build(self.canvas.db_for(project))
            if token is not None:
                self.canvas.read_cache.put(key, token, cached)
        return cached

    def _read(self, db, project, workspace, version_id):
        if not isinstance(version_id, str) or not VERSION_ID.fullmatch(version_id):
            raise ValueError("Neplatná verze plátna.")
        row = db.execute("SELECT * FROM canvas_versions WHERE id=? AND project_id=? AND workspace_id=?", (version_id, project, workspace)).fetchone()
        if row is None:
            raise ValueError("Verze plátna neexistuje.")
        graph, state = json.loads(row["graph"]), json.loads(row["state"])
        snapshot = json.loads(row["snapshot"]) if row["snapshot"] else None
        if digest(graph) != row["graph_digest"] or digest(state) != row["state_digest"]:
            raise ValueError("Kontrola integrity uložené verze selhala.")
        if snapshot and (snapshot.get("integrity") != digest({key: value for key, value in snapshot.items() if key != "integrity"})
                         or content_digest(graph, state, snapshot) != row["content_digest"]):
            raise ValueError("Kontrola integrity obsahu verze selhala.")
        return row, graph, state, snapshot

    def read(self, project, workspace, version_id):
        with self.canvas.reading(project):
            self.canvas.view(project, workspace)
            row, graph, state, snapshot = self._read(self.canvas.db_for(project), project, workspace, version_id)
            return {"version": _summary(row), "project": project, "workspace": workspace, "graph": graph,
                    "state": state, "snapshot": snapshot, "integrity": "verified", "excluded": EXCLUDED}

    def _check(self, payload, view, stored, snapshot):
        if view["readOnly"]:
            raise ValueError(READ_ONLY)
        if payload["digest"] != view["digest"] or ("expectedToken" in payload and payload["expectedToken"] != current_token(view["graph"], stored, snapshot)):
            raise ValueError(CHANGED)

    def save(self, payload, *, actor="human"):
        author = _payload(payload, SAVE_KEYS)
        project, workspace = payload["project"], payload["workspace"]
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                view, stored, snapshot = self._capture(db, project, workspace)
                self._check(payload, view, stored, snapshot)
                if actor != "human" and not self._dirty(db, project, workspace, view, stored, snapshot):
                    raise ValueError("Plátno se od poslední verze nezměnilo; agent verzi bez změn neukládá.")
                version = self._insert(db, project, workspace, author, view["graph"], stored["state"], snapshot, actor)
                return {"version": version, "dirty": False, "currentToken": current_token(view["graph"], stored, snapshot),
                        "binding": "workspace-token" if "expectedToken" in payload else "legacy-unbound"}

    def restore(self, payload):
        author = _payload(payload, RESTORE_KEYS)
        if "expectedToken" not in payload:
            raise ValueError("Obnovení vyžaduje expectedToken. Nejprve načtěte aktuální historii pracovního prostoru.")
        project, workspace = payload["project"], payload["workspace"]
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            graph_file = None
            if project != "draft" and self.canvas.project_hub.source_info(project)["sourceKind"] == "git":
                # Graf Git pracovního prostoru leží v datech plátna; worktree se obnovou nemění.
                self.canvas.location(project, workspace)
                graph_file = self.canvas.graph_file(project, workspace)
            with db:
                db.execute("BEGIN IMMEDIATE")
                current, stored, captured = self._capture(db, project, workspace)
                self._check(payload, current, stored, captured)
                row, graph, state, snapshot = self._read(db, project, workspace, payload["versionId"])
                if snapshot:
                    snapshot = {**snapshot, "records": with_later_stores(snapshot["records"])}
                files, drawings = preflight(self.canvas, db, project, workspace, graph, state, snapshot, current, stored)
                if snapshot:
                    check_closed_records(stored["state"], state, snapshot["records"], captured["records"])
                # Svěřenou autonomii mění jen člověk cestou /autonomy; obnova verze nesmí vrátit
                # odvolaný souhlas (upgrade-opora #30), proto se vždy převezme z aktuálního stavu.
                state = {key: value for key, value in state.items() if key != "autonomy"}
                if stored["state"].get("autonomy"):
                    state["autonomy"] = stored["state"]["autonomy"]
                # Back up only after scope/read-only/symlink checks. The explicit
                # commit below remains inside file rollback, including commit failures.
                with file_rollback([*files, *([graph_file] if graph_file else [])]):
                    if self._dirty(db, project, workspace, current, stored, captured):
                        self._insert(db, project, workspace, author + BEFORE_RESTORE, current["graph"], stored["state"], captured)
                    timestamp = _now()
                    write_content(db, project, workspace, snapshot, captured, files, drawings, timestamp)
                    if stored["state"] != state:
                        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)", (project, workspace, stored["revision"] + 1, encode(state), timestamp))
                    self.canvas.save_graph(project, workspace, graph, current["digest"], undo=True, _commit=False)
                    view, restored, after = self._capture(db, project, workspace)
                    result = {"view": view, "stateRevision": restored["revision"], "currentToken": current_token(view["graph"], restored, after),
                              "restoredVersionId": row["id"], "coverage": "full" if snapshot else "legacy-partial",
                              "binding": "workspace-token" if "expectedToken" in payload else "legacy-unbound"}
                    db.commit()
                    return result
