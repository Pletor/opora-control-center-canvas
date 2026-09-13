import uuid
from datetime import UTC, datetime

from backend.domain.graph.graph import valid_id

_ID_FIELDS = ("sourceId", "runId")
REQUIRED_FIELDS = {
    "project",
    "workspace",
    "layer",
    "nodeId",
    "sourceId",
    "runId",
    "sessionId",
    "expectedRevision",
    "confirmed",
}


def _valid_opaque_id(value, *, allow_none=False):
    if value is None:
        return allow_none
    return isinstance(value, str) and 1 <= len(value) <= 200 and "/" not in value and "\\" not in value


class AgentBindings:
    """Explicitní vazba {project, workspace, layer, nodeId, sourceId, runId, sessionId?} v Canvas.

    Vazbu na uzel nikdy neodvozuje z názvu ani z časové shody; vždy vyžaduje explicitní
    potvrzení a existenci uzlu v aktuálním grafu daného workspace.
    """

    def __init__(self, canvas, known_sources):
        self.canvas = canvas
        self.known_sources = frozenset(known_sources)
        canvas.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_bindings(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                layer TEXT NOT NULL, node_id TEXT NOT NULL, source_id TEXT NOT NULL,
                run_id TEXT NOT NULL, session_id TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_binding_scopes(
                project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
                revision INTEGER NOT NULL, PRIMARY KEY(project_id, workspace_id, node_id)
            );
            """
        )
        canvas.db.commit()

    def _scope_revision(self, pid, wid, node_id):
        row = self.canvas.db.execute(
            "SELECT revision FROM agent_binding_scopes WHERE project_id=? AND workspace_id=? AND node_id=?",
            (pid, wid, node_id),
        ).fetchone()
        return row["revision"] if row else 0

    def _node_exists(self, pid, wid, node_id):
        view = self.canvas.view(pid, wid)
        if view["readOnly"]:
            raise ValueError("Main je pouze pro čtení. Vazbu na agenta nelze uložit.")
        return view["graph"], any(n["id"] == node_id for n in view["graph"]["nodes"])

    def bind(self, payload):
        if not isinstance(payload, dict) or set(payload) != REQUIRED_FIELDS:
            raise ValueError("Neplatný formát vazby na agenta.")
        if payload["confirmed"] is not True:
            raise ValueError("Vazba na běh agenta vyžaduje explicitní potvrzení.")
        pid, wid, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        layer = payload["layer"]
        if not isinstance(layer, str) or len(layer) > 80 or (layer and not valid_id(layer)):
            raise ValueError("Neplatná vrstva vazby.")
        if not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")
        if payload["sourceId"] not in self.known_sources:
            raise ValueError("Neznámý zdroj běhu agenta.")
        if not _valid_opaque_id(payload["runId"]):
            raise ValueError("Neplatný identifikátor běhu.")
        if not _valid_opaque_id(payload["sessionId"], allow_none=True):
            raise ValueError("Neplatný identifikátor session.")
        if type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 0:
            raise ValueError("Neplatná očekávaná revize vazby.")
        with self.canvas.lock, self.canvas.db:
            self.canvas.db.execute("BEGIN IMMEDIATE")
            _graph, exists = self._node_exists(pid, wid, node_id)
            if not exists:
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            if layer and not any(n["id"] == layer for n in _graph["nodes"]):
                raise ValueError("Vrstva vazby v tomto pracovním prostoru neexistuje.")
            revision = self._scope_revision(pid, wid, node_id)
            if revision != payload["expectedRevision"]:
                raise ValueError("Vazby na tomto uzlu se změnily v jiném okně. Obnovte je.")
            self.canvas.db.execute(
                "INSERT INTO agent_bindings VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    pid,
                    wid,
                    layer,
                    node_id,
                    payload["sourceId"],
                    payload["runId"],
                    payload["sessionId"],
                    datetime.now(UTC).isoformat(),
                ),
            )
            self.canvas.db.execute(
                "INSERT INTO agent_binding_scopes VALUES(?,?,?,1) ON CONFLICT(project_id,workspace_id,node_id) DO UPDATE SET revision=revision+1",
                (pid, wid, node_id),
            )
        return self.list_for_node(pid, wid, node_id)

    def list_for_node(self, pid, wid, node_id):
        if not valid_id(node_id):
            raise ValueError("Neplatný identifikátor uzlu.")
        with self.canvas.lock:
            revision = self._scope_revision(pid, wid, node_id)
            rows = self.canvas.db.execute(
                """SELECT id,source_id,run_id,session_id,layer,created_at FROM agent_bindings
                   WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY created_at""",
                (pid, wid, node_id),
            ).fetchall()
        return {
            "revision": revision,
            "items": [
                {
                    "bindingId": r["id"],
                    "sourceId": r["source_id"],
                    "runId": r["run_id"],
                    "sessionId": r["session_id"],
                    "layer": r["layer"],
                    "createdAt": r["created_at"],
                }
                for r in rows
            ],
        }

    def _descendants(self, graph, sector_id):
        children = {}
        for node in graph["nodes"]:
            children.setdefault(node["parentId"], []).append(node["id"])
        out, stack = set(), [sector_id]
        while stack:
            current = stack.pop()
            if current in out:
                continue
            out.add(current)
            stack.extend(children.get(current, []))
        return out

    def sector_aggregate(self, pid, wid, sector_id):
        with self.canvas.lock:
            view = self.canvas.view(pid, wid)
            if not any(n["id"] == sector_id for n in view["graph"]["nodes"]):
                raise ValueError("Sektor v tomto pracovním prostoru neexistuje.")
            node_ids = self._descendants(view["graph"], sector_id)
            placeholders = ",".join("?" * len(node_ids))
            rows = self.canvas.db.execute(
                f"""SELECT DISTINCT source_id,run_id FROM agent_bindings
                    WHERE project_id=? AND workspace_id=? AND node_id IN ({placeholders})""",
                (pid, wid, *node_ids),
            ).fetchall()
        return {"items": [{"sourceId": r["source_id"], "runId": r["run_id"]} for r in rows]}

    def _ancestors(self, graph, node_id):
        parents = {n["id"]: n["parentId"] for n in graph["nodes"]}
        out, current, seen = [], node_id, set()
        while current is not None and current not in seen:
            seen.add(current)
            out.append(current)
            current = parents.get(current)
        return out

    def is_bound(self, pid, wid, node_id, source_id, run_id, graph):
        """Je `run_id` z `source_id` vázán přímo na `node_id`, nebo na některý jeho
        sektor (předka)? Používá `AgentActivityJournal`, aby zápis aktivity vyžadoval
        skutečnou existující vazbu běhu na uzel/sektor, ne jen libovolné ID od klienta."""
        ancestors = self._ancestors(graph, node_id)
        placeholders = ",".join("?" * len(ancestors))
        with self.canvas.lock:
            row = self.canvas.db.execute(
                f"""SELECT 1 FROM agent_bindings
                    WHERE project_id=? AND workspace_id=? AND source_id=? AND run_id=?
                    AND node_id IN ({placeholders}) LIMIT 1""",
                (pid, wid, source_id, run_id, *ancestors),
            ).fetchone()
        return row is not None

    def bound_run_keys(self, source_id):
        with self.canvas.lock:
            rows = self.canvas.db.execute(
                "SELECT DISTINCT run_id FROM agent_bindings WHERE source_id=?", (source_id,)
            ).fetchall()
        return {r["run_id"] for r in rows}

    def filter_unbound(self, candidates):
        cache = {}
        out = []
        for item in candidates:
            source_id = item["sourceId"]
            if source_id not in cache:
                cache[source_id] = self.bound_run_keys(source_id)
            if item["runId"] not in cache[source_id]:
                out.append(item)
        return out
