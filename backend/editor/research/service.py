"""Workspace research graph. Atomic append-only updates with CAS and replay keys."""
import hashlib
import json
from datetime import UTC, datetime

from backend.editor.research import model, question_journal, events

TABLES = {"card": "research_card_revisions", "edge": "research_edge_revisions"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _scope(service, project, workspace):
    model.identifier(project); model.identifier(workspace)
    return service.view(project, workspace)


def _latest(db, project, workspace, entity):
    table = TABLES[entity]
    rows = db.execute(f"SELECT payload FROM {table} t WHERE project_id=? AND workspace_id=? AND revision="
                      f"(SELECT MAX(revision) FROM {table} r WHERE r.project_id=t.project_id "
                      "AND r.workspace_id=t.workspace_id AND r.id=t.id)", (project, workspace))
    return {value["id"]: value for value in (json.loads(row[0]) for row in rows)}


def listing(service, project, workspace, archived=False):
    _scope(service, project, workspace)
    question_journal.reconcile(service, project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        cards = _latest(db, project, workspace, "card")
        selected = {key: item for key, item in cards.items() if archived or not item["archived"]}
        edges = _latest(db, project, workspace, "edge")
        visible_edges = [e for e in edges.values() if (archived or not e["archived"])
                         and e["fromId"] in selected and e["toId"] in selected]
        counts = {id: {"incoming": 0, "outgoing": 0} for id in selected}
        for edge in visible_edges:
            counts[edge["fromId"]]["outgoing"] += 1
            counts[edge["toId"]]["incoming"] += 1
        return {"cards": [{**model.header(c), "relationCounts": counts[c["id"]]} for c in selected.values()],
                "edges": visible_edges}


def detail(service, project, workspace, id, revision=None):
    _scope(service, project, workspace); model.identifier(id)
    if revision is not None and (type(revision) is not int or revision < 1):
        model.fail("revision must be a positive integer.")
    question_journal.reconcile(service, project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        rows = db.execute("SELECT payload FROM research_card_revisions WHERE project_id=? AND workspace_id=? "
                          "AND id=? ORDER BY revision", (project, workspace, id)).fetchall()
        history = [json.loads(row[0]) for row in rows]
        found = next((c for c in reversed(history) if revision is None or c["revision"] == revision), None)
        if found is None:
            model.fail("Research card or revision not found in this workspace.", 404, "research_not_found")
        edges = _latest(db, project, workspace, "edge")
        return {"card": found, "history": [{k: c[k] for k in ("revision", "updatedAt", "by", "archived")}
                                            for c in history],
                "edges": [e for e in edges.values() if id in (e["fromId"], e["toId"])]}


def edge_detail(service, project, workspace, id, revision=None):
    """Read an immutable semantic edge revision and its complete revision index."""
    _scope(service, project, workspace)
    model.identifier(id)
    if revision is not None and (type(revision) is not int or revision < 1):
        model.fail("revision must be a positive integer.")
    question_journal.reconcile(service, project, workspace)
    with service.reading(project):
        rows = service.db_for(project).execute(
            "SELECT payload FROM research_edge_revisions WHERE project_id=? AND workspace_id=? AND id=? ORDER BY revision",
            (project, workspace, id)).fetchall()
        history = [json.loads(row[0]) for row in rows]
        found = next((edge for edge in reversed(history) if revision is None or edge["revision"] == revision), None)
        if found is None:
            model.fail("Research edge or revision not found in this workspace.", 404, "research_not_found")
        return {"edge": found, "history": [{k: edge[k] for k in ("revision", "updatedAt", "by", "archived")}
                                            for edge in history]}


def _references(cards, edges):
    for edge in edges.values():
        for id in [edge["fromId"], edge["toId"], *edge["evidenceIds"]]:
            if id not in cards:
                model.fail("Edge endpoint/evidence must reference a card in this workspace: " + id,
                           409, "research_reference")


def _batch(db, project, workspace, operations, actor, agent):
    records = {kind: _latest(db, project, workspace, kind) for kind in TABLES}
    changed = {"card": [], "edge": []}
    seen = set()
    now = datetime.now(UTC).isoformat()
    for op in operations:
        if not isinstance(op, dict) or op.get("op") not in ("card", "edge", "archive"):
            model.fail("Unknown research operation.")
        kind = op.get("entity") if op["op"] == "archive" else op["op"]
        if not isinstance(kind, str) or kind not in TABLES:
            model.fail("entity must be card or edge.")
        id = model.identifier(op.get("id"))
        if (kind, id) in seen:
            model.fail("Each entity may appear only once in a batch.")
        seen.add((kind, id))
        expected = op.get("expectedRevision")
        if type(expected) is not int or expected < 0:
            model.fail("expectedRevision must be a nonnegative integer.")
        old = records[kind].get(id)
        if expected != (old["revision"] if old else 0):
            model.fail("Revision conflict: " + id, 409, "research_conflict")
        if op["op"] == "archive":
            model.shape(op, {"op", "entity", "id", "expectedRevision", "archived"})
            if old is None or type(op["archived"]) is not bool:
                model.fail("Archive requires an existing entity and boolean archived.")
            value = {**old, "archived": op["archived"]}
        else:
            fields = model.CARD if kind == "card" else model.EDGE
            model.shape(op, fields | {"op", "id", "expectedRevision"})
            value = {k: op[k] for k in fields}
            (model.card if kind == "card" else model.edge)(value)
            value["archived"] = old["archived"] if old else False
        value.update(id=id, revision=expected + 1, createdAt=old["createdAt"] if old else now,
                     updatedAt=now, by=agent or "heart" if actor == "agent" else actor)
        records[kind][id] = value
        changed[kind].append(value)
    _references(records["card"], records["edge"])
    for kind, values in changed.items():
        for value in values:
            db.execute(f"INSERT INTO {TABLES[kind]} (project_id,workspace_id,id,revision,payload) VALUES (?,?,?,?,?)",
                       (project, workspace, value["id"], value["revision"], _json(value)))
    return {"cards": changed["card"], "edges": changed["edge"]}


def apply(service, payload, actor, agent=None):
    """Trusted internal entrypoint; HTTP router authenticates heart/human before invoking."""
    if actor not in ("human", "agent"):
        model.fail("Research writes require an authenticated human or heart.", 403, "research_writer")
    model.shape(payload, {"project", "workspace", "key", "operations"}, {"continuation", "scopeNodeId"})
    project, workspace = payload["project"], payload["workspace"]
    model.text(payload["key"], "key", 200, False)
    ops = payload["operations"]
    if not isinstance(ops, list) or not 1 <= len(ops) <= 1000:
        model.fail("operations must contain 1 to 1000 entries.")
    scope_node = payload.get("scopeNodeId")
    if scope_node is not None:
        model.identifier(scope_node)
    hashed = {"operations": ops, **{key: payload[key] for key in ("continuation", "scopeNodeId") if key in payload}} if any(key in payload for key in ("continuation", "scopeNodeId")) else ops
    digest = hashlib.sha256(_json(hashed).encode()).hexdigest()
    with service.graph_lock_for(project):
        view = _scope(service, project, workspace)
        if scope_node is not None:
            if not any(n["id"] == scope_node and n["kind"] in ("node", "sector") for n in view["graph"]["nodes"]):
                model.fail("Research scope node does not exist in this workspace.", 404, "research_scope")
            ops = [{**op, "refs": {**op["refs"], "nodeIds": op["refs"]["nodeIds"] + ([] if scope_node in op["refs"]["nodeIds"] else [scope_node])}}
                   if op.get("op") == "card" and op.get("expectedRevision") == 0 and isinstance(op.get("refs"), dict)
                   and isinstance(op["refs"].get("nodeIds"), list) else op for op in ops]
        db = service.db_for(project)
        with service.lock_for(project), db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT digest,response FROM research_batches WHERE project_id=? AND workspace_id=? AND key=?",
                               (project, workspace, payload["key"])).fetchone()
            if prior:
                if prior[0] != digest:
                    model.fail("Idempotency key already used with different operations.", 409, "research_key_conflict")
                return json.loads(prior[1])
            result = _batch(db, project, workspace, ops, actor, agent)
            if "continuation" in payload:
                from backend.editor.research.continuations import create
                result["continuation"] = create(db, project, workspace, payload["continuation"], result, actor, agent)
            events.record(db, project, workspace, payload["key"], result, actor, agent)
            db.execute("INSERT INTO research_batches VALUES (?,?,?,?,?)",
                       (project, workspace, payload["key"], digest, _json(result)))
            return result
