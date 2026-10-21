"""Transactional workspace content storage, never a fallback to an older graph file.

Content can reference shared architecture nodes. Callers validate the composed graph;
this repository checks shape, canonical serialization, integrity and optimistic revision.
Enrollment and writes require the caller's transaction and never commit it.
"""
import hashlib
import json

from backend.canvas.architecture_graph import check_shape
from backend.canvas.graph import valid_id


def _encode(graph):
    check_shape(graph)
    if set(graph) != {"nodes", "edges"} or len(graph["nodes"]) > 2000 or len(graph["edges"]) > 4000:
        raise ValueError("Invalid workspace graph shape or size.")
    for collection in ("nodes", "edges"):
        identifiers = [item["id"] for item in graph[collection]]
        if not all(map(valid_id, identifiers)) or len(identifiers) != len(set(identifiers)):
            raise ValueError("Invalid or duplicate workspace graph identifiers.")
    try:
        raw = json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValueError("Workspace graph must contain finite JSON data.") from error
    return raw, fingerprint


class WorkspaceGraphAuthority:
    def __init__(self, db, project, workspace):
        if not valid_id(project) or not valid_id(workspace):
            raise ValueError("Invalid workspace graph scope.")
        self.db, self.scope = db, (project, workspace)

    def enrolled(self):
        return self.read() is not None

    def read(self):
        row = self.db.execute("SELECT revision,graph,digest FROM workspace_graph_authority"
                              " WHERE project_id=? AND workspace_id=?", self.scope).fetchone()
        if row is None:
            return None
        revision, raw, fingerprint = row
        try:
            graph = json.loads(raw)
            canonical, actual = _encode(graph)
            if type(revision) is not int or revision < 1 or raw != canonical or fingerprint != actual:
                raise ValueError("Workspace graph integrity check failed.")
        except (TypeError, ValueError) as error:
            raise ValueError("Authoritative workspace graph is corrupt; file fallback is forbidden.") from error
        return {"graph": graph, "revision": revision, "digest": fingerprint}

    def _transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError("Workspace graph mutation requires an existing transaction.")

    def enroll(self, graph):
        self._transaction()
        raw, fingerprint = _encode(graph)
        if self.enrolled():
            raise ValueError("Workspace graph is already enrolled.")
        self.db.execute("INSERT INTO workspace_graph_authority"
                        " (project_id,workspace_id,revision,graph,digest) VALUES(?,?,1,?,?)",
                        (*self.scope, raw, fingerprint))
        return self.read()

    def write(self, graph, expected_revision=None):
        self._transaction()
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 1):
            raise ValueError("Invalid expected workspace graph revision.")
        current = self.read()
        if current is None:
            raise ValueError("Workspace graph is not enrolled.")
        if expected_revision is not None and expected_revision != current["revision"]:
            raise ValueError("Workspace graph revision changed.")
        raw, fingerprint = _encode(graph)
        cursor = self.db.execute("UPDATE workspace_graph_authority SET revision=revision+1,graph=?,digest=?"
                                 " WHERE project_id=? AND workspace_id=? AND revision=?",
                                 (raw, fingerprint, *self.scope, current["revision"]))
        if cursor.rowcount != 1:
            raise ValueError("Workspace graph revision changed.")
        return self.read()
