"""Server-side auto-rebase of stale native proposals after the accepted head advances.

No global lock: each proposal is merged under its own project lock and SQLite transaction.
Outcomes are keyed by (proposal, accepted head), so a repeated tick changes nothing.
Acceptance stays human-only; this module never advances the accepted head.
Contract: docs/oporahub-auto-rebase.md."""
import os

from backend.canvas.opora_auto_rebase_apply import APPLY
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_commit_validation import _author
from database.repositories.opora_auto_rebase import AutoRebaseStore
from database.repositories.opora_changesets import ChangesetRepository

ENV_SWITCH = "OPORA_AUTO_REBASE"
SOURCES = {"spec": ("opora_spec_proposals", "parent_id"),
           "graph": ("opora_graph_proposals", "parent_revision"),
           "content": ("opora_content_proposals", "json_extract(content,'$.parentRevision')")}
BUCKETS = {"rebased": "rebased", "redundant": "redundant", "conflict": "conflicts"}


def enabled():
    return os.environ.get(ENV_SWITCH, "1") != "0"


def batch_limit():
    try:
        return max(1, min(256, int(os.environ.get("OPORA_AUTO_REBASE_BATCH", "16"))))
    except ValueError:
        return 16


def proposals(db, project, workspace):
    """Every native proposal as (kind, id, parent, createdAt) plus accepted and superseded ids."""
    rows, superseded = [], set()
    for kind, (table, parent) in SOURCES.items():
        sql = (f"SELECT id,{parent},json_extract(content,'$.createdAt'),json_extract(content,'$.supersedes')"
               f" FROM {table} WHERE project_id=? AND workspace_id=?")
        for row in db.execute(sql, (project, workspace)).fetchall():
            rows.append((kind, row[0], row[1], row[2] or ""))
            if row[3]:
                superseded.add(row[3])
    accepted = {row[0] for row in db.execute("SELECT proposal_id FROM opora_spec_revisions WHERE project_id=?"
                                             " AND workspace_id=? AND proposal_id IS NOT NULL",
                                             (project, workspace)).fetchall()}
    return rows, accepted, superseded


def stale(db, project, workspace, head):
    """Unaccepted, unsuperseded proposals whose parent is not the accepted head, oldest first."""
    rows, accepted, superseded = proposals(db, project, workspace)
    return sorted((created, kind, ident) for kind, ident, parent, created in rows
                  if parent != head and ident not in accepted and ident not in superseded)


class AutoRebase:
    def __init__(self, canvas):
        self.canvas = canvas

    def store(self, project, workspace):
        return AutoRebaseStore(self.canvas.db_for(project), project, workspace)

    def run(self, project, workspace, limit=None):
        """Merge up to `limit` unprocessed stale proposals; returns the touched ids per outcome."""
        scope({"project": project, "workspace": workspace})
        limit = batch_limit() if limit is None else limit
        summary = {"acceptedHead": None, "rebased": [], "redundant": [], "conflicts": [], "skipped": [],
                   "remaining": 0}
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            head = ChangesetRepository(db, project, workspace).head()
            summary["acceptedHead"] = head
            if head is None:
                return summary
            self._obsolete(db, project, workspace, head)
            store = AutoRebaseStore(db, project, workspace)
            settled = store.kept_accepted()
            todo = [(kind, ident) for _, kind, ident in stale(db, project, workspace, head)
                    if ident not in settled and store.outcome(kind, ident, head) is None]
            summary["remaining"] = max(0, len(todo) - limit)
            for kind, ident in todo[:limit]:
                outcome, result, reason = self._one(db, project, workspace, head, kind, ident)
                summary[BUCKETS.get(outcome, "skipped")].append(
                    {"kind": kind, "proposalId": ident, "resultId": result, "reason": reason})
        return summary

    def _one(self, db, project, workspace, head, kind, ident):
        store = AutoRebaseStore(db, project, workspace)
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("SAVEPOINT auto_rebase")
            try:
                outcome, result, conflicts, reason = APPLY[kind](self.canvas, project, workspace, ident)
            except ValueError as error:
                db.execute("ROLLBACK TO auto_rebase")
                outcome, result, conflicts, reason = "skipped", None, [], str(error)[:500]
            db.execute("RELEASE auto_rebase")
            if outcome == "conflict":
                result = store.open_conflict(kind, ident, head, conflicts, stamp())
            store.record(kind, ident, head, outcome, result, reason, stamp())
        return outcome, result, reason

    def _obsolete(self, db, project, workspace, head):
        store = AutoRebaseStore(db, project, workspace)
        _, accepted, superseded = proposals(db, project, workspace)
        stale_conflicts = [item["id"] for item in store.conflicts("open", limit=10000)
                           if item["acceptedHead"] != head or item["proposalId"] in accepted
                           or item["proposalId"] in superseded]
        if not stale_conflicts:
            return
        with db:
            db.execute("BEGIN IMMEDIATE")
            for conflict_id in stale_conflicts:
                store.transition(conflict_id, "obsolete", None, stamp())

    def conflicts(self, project, workspace, status=None):
        scope({"project": project, "workspace": workspace})
        if status not in (None, "open", "resolved", "obsolete"):
            raise ValueError("Unknown conflict status filter.")
        with self.canvas.lock_for(project):
            store = self.store(project, workspace)
            return {"items": store.conflicts(status),
                    "acceptedHead": ChangesetRepository(store.db, project, workspace).head(), "enabled": enabled()}

    def conflict(self, project, workspace, conflict_id):
        scope({"project": project, "workspace": workspace})
        identifier(conflict_id)
        with self.canvas.lock_for(project):
            return self.store(project, workspace).conflict(conflict_id)

    def resolve(self, conflict_id, payload, by):
        """Close an open conflict (human or agent): link a normal new proposal on the current head
        (`resolutionProposalId`), or `keep: "accepted"` when the accepted head already decided the fields
        (no resolution proposal, the head stays untouched)."""
        by = _author(by, allow_agent=True)
        fields = set(payload) if isinstance(payload, dict) else set()
        if fields not in ({"project", "workspace", "resolutionProposalId"}, {"project", "workspace", "keep"}):
            raise ValueError("Invalid conflict resolution fields: exactly one of resolutionProposalId or keep.")
        project, workspace = scope(payload)
        identifier(conflict_id)
        keep = "keep" in fields
        if keep and payload["keep"] != "accepted":
            raise ValueError("keep must be \"accepted\".")
        resolution = None if keep else payload["resolutionProposalId"]
        if not keep:
            identifier(resolution)
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            db = self.canvas.db_for(project)
            store = AutoRebaseStore(db, project, workspace)
            conflict = store.conflict(conflict_id)
            head = ChangesetRepository(db, project, workspace).head()
            if conflict["status"] != "open":
                raise ValueError("Only an open conflict can be resolved.")
            if keep:
                if conflict["acceptedHead"] != head:
                    raise ValueError("Conflict was recorded against an older accepted head.")
            else:
                rows, _, _ = proposals(db, project, workspace)
                parents = {ident: parent for _, ident, parent, _ in rows}
                if resolution == conflict["proposalId"] or parents.get(resolution, "missing") != head:
                    raise ValueError("Resolution must be a different proposal created on the current accepted head.")
            with db:
                db.execute("BEGIN IMMEDIATE")
                store.transition(conflict_id, "resolved", resolution, stamp())
            return {**store.conflict(conflict_id), "resolvedBy": by}
