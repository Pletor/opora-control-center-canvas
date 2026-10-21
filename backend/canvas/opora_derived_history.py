"""Derived card history and blame, computed from accepted changesets with a recomputable cache.

Every accepted revision is projected to per-card keys (spec fields, graph node fields, incident
edges, content entries) and diffed against its parent's projection. The diff is cached in
`opora_derived_card_changes` keyed by revision; it is immutable input-derived data and
`rebuild` recomputes it. No local copy of the plan is needed: history and blame are API reads.
Contract: docs/oporahub-auto-rebase.md ("Odvozená data")."""
import hashlib
import json

from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_graph_records import combined
from backend.canvas.opora_hub_store import canonical
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_content_records import ContentRecords
from database.repositories.opora_graph_proposals import GraphProposals

VERSION = 1
CHAIN_LIMIT = 10000
PROPOSAL_TABLES = (("spec", "opora_spec_proposals"), ("graph", "opora_graph_proposals"),
                   ("content", "opora_content_proposals"))


def _digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:24]


def chain(db, project, workspace, head):
    """Accepted revision ids from the root to `head` (oldest first)."""
    parents = dict(db.execute("SELECT id,parent_id FROM opora_spec_revisions WHERE project_id=? AND workspace_id=?",
                              (project, workspace)).fetchall())
    result, current = [], head
    while current is not None:
        if current not in parents or len(result) >= CHAIN_LIMIT:
            raise ValueError("Accepted history is incomplete or exceeds the derived-history bound.")
        result.append(current)
        current = parents[current]
    return result[::-1]


class Projector:
    """Per-card key → value digest for one accepted revision; manifests are cached by id."""

    def __init__(self, db, project, workspace):
        self.repo = ChangesetRepository(db, project, workspace)
        self.graphs, self.contents, self.manifests = GraphProposals(db, project, workspace), \
            ContentRecords(db, project, workspace), {}

    def _manifest(self, kind, identifier):
        if identifier not in self.manifests:
            store = self.graphs if kind == "graph" else self.contents
            self.manifests[identifier] = store.read(identifier, manifest=True)
        return self.manifests[identifier]

    def project(self, revision_id):
        record, cards = self.repo.read(revision_id), {}
        for document in record["documents"]:
            for name, value in document["fields"].items():
                cards.setdefault(document["nodeId"], {})[f"spec:{name}"] = _digest(value)
        if record.get("graphManifestId"):
            graph = combined(self._manifest("graph", record["graphManifestId"]))
            for node in graph["nodes"]:
                for name, value in node.items():
                    if name != "id":
                        cards.setdefault(node["id"], {})[f"graph:node:{name}"] = _digest(value)
            for edge in graph["edges"]:
                for end in {edge["source"], edge["target"]}:
                    cards.setdefault(end, {})[f"graph:edge:{edge['id']}"] = _digest(edge)
        if record.get("contentManifestId"):
            for entry in self._manifest("content", record["contentManifestId"])["entries"]:
                if entry["target"]:
                    key = f"content:{entry['kind']}:{entry['field']}"
                    cards.setdefault(entry["target"], {})[key] = _digest(entry["value"])
        return record, cards


def _delta(before, after):
    result = {}
    for card in set(before) | set(after):
        old, new = before.get(card, {}), after.get(card, {})
        changed = {key: new.get(key) for key in set(old) | set(new) if old.get(key) != new.get(key)}
        if changed:
            result[card] = changed
    return result


def ensure(db, project, workspace, ids):
    """Derive missing revisions of `ids` (oldest first); caller holds the project lock."""
    done = {row[0] for row in db.execute("SELECT revision_id FROM opora_derived_revisions WHERE project_id=?"
                                         " AND workspace_id=? AND version=?", (project, workspace, VERSION))}
    missing = [index for index, revision in enumerate(ids) if revision not in done]
    if not missing:
        return
    projector, previous = Projector(db, project, workspace), None
    with db:
        db.execute("BEGIN IMMEDIATE")
        for index in range(missing[0], len(ids)):
            revision = ids[index]
            if previous is None:
                previous = projector.project(ids[index - 1])[1] if index else {}
            record, cards = projector.project(revision)
            if revision not in done:
                db.execute("DELETE FROM opora_derived_card_changes WHERE project_id=? AND workspace_id=? AND revision_id=?",
                           (project, workspace, revision))
                for card, changed in sorted(_delta(previous, cards).items()):
                    db.execute("INSERT INTO opora_derived_card_changes VALUES(?,?,?,?,?)",
                               (project, workspace, revision, card, canonical(changed)))
                db.execute("INSERT OR REPLACE INTO opora_derived_revisions VALUES(?,?,?,?,?)",
                           (project, workspace, revision, record.get("parentRevision"), VERSION))
            previous = cards


def _proposal(db, project, workspace, identifier):
    for kind, table in PROPOSAL_TABLES:
        row = db.execute(f"SELECT content FROM {table} WHERE project_id=? AND workspace_id=? AND id=?",
                         (project, workspace, identifier)).fetchone()
        if row:
            return kind, json.loads(row[0])
    return None, None


def _meta(db, project, workspace, record):
    kind, proposal = _proposal(db, project, workspace, record["proposalId"]) if record.get("proposalId") else (None, None)
    original, hops = proposal, 0
    while original and original.get("supersedes") and hops < 64:
        _, older = _proposal(db, project, workspace, original["supersedes"])
        if older is None:
            break
        original, hops = older, hops + 1
    return {"revisionId": record["id"], "parentRevision": record.get("parentRevision"), "revisionKind": record["kind"],
            "proposalId": record.get("proposalId"), "proposalKind": kind, "subject": record.get("subject"),
            "author": proposal.get("by") if proposal else record.get("by"),
            "originalAuthor": original.get("by") if original else record.get("by"),
            "rebasedFrom": proposal.get("supersedes") if proposal else None,
            "acceptedBy": record.get("by"), "acceptedAt": record.get("createdAt")}


class DerivedHistory:
    def __init__(self, canvas):
        self.canvas = canvas

    def _changes(self, project, workspace, card):
        scope({"project": project, "workspace": workspace})
        if not isinstance(card, str) or not 1 <= len(card) <= 128:
            raise ValueError("Invalid card id.")
        db = self.canvas.db_for(project)
        repo = ChangesetRepository(db, project, workspace)
        head = repo.head()
        ids = chain(db, project, workspace, head) if head else []
        ensure(db, project, workspace, ids)
        rows = dict(db.execute("SELECT revision_id,content FROM opora_derived_card_changes WHERE project_id=?"
                               " AND workspace_id=? AND card_id=?", (project, workspace, card)).fetchall())
        return db, repo, head, [(revision, json.loads(rows[revision])) for revision in ids if revision in rows]

    def history(self, project, workspace, card):
        with self.canvas.lock_for(project):
            db, repo, head, changes = self._changes(project, workspace, card)
            return {"cardId": card, "acceptedHead": head, "items": [
                {**_meta(db, project, workspace, repo.read(revision)), "changedKeys": sorted(changed)}
                for revision, changed in changes]}

    def blame(self, project, workspace, card):
        with self.canvas.lock_for(project):
            db, repo, head, changes = self._changes(project, workspace, card)
            current = Projector(db, project, workspace).project(head)[1].get(card, {}) if head else {}
            owners, meta = {}, {}
            for revision, changed in reversed(changes):
                for key in changed:
                    if key in current and key not in owners:
                        owners[key] = revision
            for revision in set(owners.values()):
                meta[revision] = _meta(db, project, workspace, repo.read(revision))
            return {"cardId": card, "acceptedHead": head,
                    "items": [{"key": key, **meta[owners[key]]} for key in sorted(owners)]}

    def rebuild(self, project, workspace):
        scope({"project": project, "workspace": workspace})
        with self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            with db:
                db.execute("BEGIN IMMEDIATE")
                for table in ("opora_derived_card_changes", "opora_derived_revisions"):
                    db.execute(f"DELETE FROM {table} WHERE project_id=? AND workspace_id=?",
                               (project, workspace))
            head = ChangesetRepository(db, project, workspace).head()
            ids = chain(db, project, workspace, head) if head else []
            ensure(db, project, workspace, ids)
            return {"acceptedHead": head, "revisions": len(ids)}
