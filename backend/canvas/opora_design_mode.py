"""Režim design karty (docs/design-nahled.md §2): `brand` (výchozí, karta drží DESIGN.md) nebo `explore`.

`explore` je experiment / nový směr značky: karta z DESIGN.md nečerpá a odevzdá návrh nového DESIGN.md vedle
screenshotů. Režim mění jen člověk v UI (tlačítka „Podle brandu“ / „Nový směr“); každá změna zvýší revizi, takže
se dá poznat, za jakého režimu doklad vznikl. Chybějící řádek znamená `brand` s revizí 0."""
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_design_preview_validation import MODES
from backend.canvas.opora_execution_validation import validate

DEFAULT = {"mode": "brand", "revision": 0, "by": None, "updatedAt": None}


def read(db, project, workspace, node_id):
    row = db.execute("SELECT mode,revision,by,updated_at FROM opora_design_modes"
                     " WHERE project_id=? AND workspace_id=? AND node_id=?", (project, workspace, node_id)).fetchone()
    if row is None:
        return dict(DEFAULT)
    return {"mode": row[0], "revision": row[1], "by": row[2], "updatedAt": row[3]}


def _has_node(service, project, workspace, node_id):
    graph = service.view(project, workspace)["graph"]
    return any(isinstance(node, dict) and node.get("id") == node_id for node in graph.get("nodes", []))


def set_mode(service, payload, by):
    """`{project, workspace, nodeId, mode}` od člověka → `{nodeId, mode, revision, by, updatedAt, changed}`."""
    project, workspace = validate(payload, {"nodeId", "mode"})
    node_id, mode = payload["nodeId"], payload["mode"]
    if mode not in MODES:
        raise ValueError("design mode must be brand or explore.")
    if not _has_node(service, project, workspace, node_id):
        raise ValueError("The card does not exist in this workspace.")
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        with db:
            current = read(db, project, workspace, node_id)
            if current["mode"] == mode:
                return {"nodeId": node_id, **current, "changed": False}
            value = {"mode": mode, "revision": current["revision"] + 1, "by": by, "updatedAt": stamp()}
            db.execute("INSERT OR REPLACE INTO opora_design_modes VALUES(?,?,?,?,?,?,?)",
                       (project, workspace, node_id, mode, value["revision"], by, value["updatedAt"]))
            return {"nodeId": node_id, **value, "changed": True}
