"""Auto-rebase outcomes and conflict records; callers own locks and transactions."""
import json

from backend.canvas.opora_hub_store import canonical, content_id

KINDS = ("spec", "graph", "content")
OUTCOMES = ("rebased", "redundant", "conflict", "skipped")


class AutoRebaseStore:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def outcome(self, kind, proposal_id, head):
        row = self.db.execute("SELECT outcome,result_id,reason FROM opora_auto_rebase_outcomes WHERE project_id=?"
                              " AND workspace_id=? AND proposal_kind=? AND proposal_id=? AND accepted_head=?",
                              (*self.scope, kind, proposal_id, head)).fetchone()
        return None if row is None else {"outcome": row[0], "resultId": row[1], "reason": row[2]}

    def record(self, kind, proposal_id, head, outcome, result_id, reason, at):
        if not self.db.in_transaction:
            raise RuntimeError("Auto-rebase outcomes require a caller transaction.")
        if kind not in KINDS or outcome not in OUTCOMES:
            raise ValueError("Invalid auto-rebase outcome.")
        inserted = self.db.execute("INSERT OR IGNORE INTO opora_auto_rebase_outcomes VALUES(?,?,?,?,?,?,?,?,?)",
                                   (*self.scope, kind, proposal_id, head, outcome, result_id, reason, at)).rowcount == 1
        if inserted and outcome != "skipped":
            # Exactly once per (proposal, accepted head).
            from backend.canvas.opora_events import emit_event
            emit_event(self.db, project_id=self.scope[0], workspace_id=self.scope[1],
                       kind="autorebase.conflict" if outcome == "conflict" else "autorebase.done",
                       data={"proposalKind": kind, "proposalId": proposal_id, "acceptedHead": head,
                             "outcome": outcome, "resultId": result_id, "reason": reason})

    def redundant(self):
        rows = self.db.execute("SELECT DISTINCT proposal_id FROM opora_auto_rebase_outcomes WHERE project_id=?"
                               " AND workspace_id=? AND outcome='redundant'", self.scope).fetchall()
        return {row[0] for row in rows}

    def open_conflict(self, kind, proposal_id, head, items, at):
        body = {"proposalKind": kind, "proposalId": proposal_id, "acceptedHead": head, "items": items}
        identifier = content_id({"scope": list(self.scope), **body})
        self.db.execute("INSERT OR IGNORE INTO opora_auto_rebase_conflicts VALUES(?,?,?,?,?,?,'open',NULL,?,?,?)",
                        (*self.scope, identifier, kind, proposal_id, head, at, at, canonical(body)))
        return identifier

    def conflicts(self, status=None, limit=100):
        sql = "SELECT id,status,resolution_id,created_at,updated_at,content FROM opora_auto_rebase_conflicts" \
              " WHERE project_id=? AND workspace_id=?"
        args = list(self.scope)
        if status:
            sql += " AND status=?"
            args.append(status)
        rows = self.db.execute(sql + " ORDER BY created_at,id LIMIT ?", (*args, limit)).fetchall()
        return [self._row(row) for row in rows]

    def conflict(self, identifier):
        row = self.db.execute("SELECT id,status,resolution_id,created_at,updated_at,content FROM"
                              " opora_auto_rebase_conflicts WHERE project_id=? AND workspace_id=? AND id=?",
                              (*self.scope, identifier)).fetchone()
        if row is None:
            raise ValueError("Auto-rebase conflict does not exist in this scope.")
        return self._row(row)

    def transition(self, identifier, status, resolution_id, at):
        if not self.db.in_transaction:
            raise RuntimeError("Conflict transitions require a caller transaction.")
        changed = self.db.execute("UPDATE opora_auto_rebase_conflicts SET status=?,resolution_id=?,updated_at=?"
                                  " WHERE project_id=? AND workspace_id=? AND id=? AND status='open'",
                                  (status, resolution_id, at, *self.scope, identifier)).rowcount
        return changed == 1

    @staticmethod
    def _row(row):
        body = json.loads(row[5])
        return {"id": row[0], "status": row[1], "resolutionProposalId": row[2], "createdAt": row[3],
                "updatedAt": row[4], **body}
