"""Execution records share card_leases; enrollment counters survive every release."""
import json


class Executions:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def read(self, identifier):
        row = self.db.execute("SELECT record FROM opora_executions WHERE id=? AND project_id=? AND workspace_id=?",
                              (identifier, *self.scope)).fetchone()
        if row is None:
            raise ValueError("Execution does not exist in this scope.")
        return json.loads(row[0])

    def replay(self, owner, request):
        row = self.db.execute("SELECT request_digest,record FROM opora_executions"
                              " WHERE project_id=? AND workspace_id=? AND owner=? AND request_id=?",
                              (*self.scope, owner, request)).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def next_epoch(self, node):
        self.db.execute("INSERT INTO opora_execution_epochs VALUES(?,?,?,1)"
                        " ON CONFLICT(project_id,workspace_id,node_id) DO UPDATE SET epoch=epoch+1",
                        (*self.scope, node))
        return self.db.execute("SELECT epoch FROM opora_execution_epochs"
                               " WHERE project_id=? AND workspace_id=? AND node_id=?", (*self.scope, node)).fetchone()[0]

    def insert(self, record, owner, request, digest):
        self.db.execute("INSERT INTO opora_executions VALUES(?,?,?,?,?,?,?,?)",
                        (record["executionId"], *self.scope, record["nodeId"], owner, request, digest,
                         json.dumps(record, ensure_ascii=False)))

    def save(self, record):
        self.db.execute("UPDATE opora_executions SET record=? WHERE id=? AND project_id=? AND workspace_id=?",
                        (json.dumps(record, ensure_ascii=False), record["executionId"], *self.scope))

    def receipt(self, identifier, request):
        row = self.db.execute("SELECT digest,record FROM opora_execution_results WHERE execution_id=? AND request_id=?",
                              (identifier, request)).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def insert_receipt(self, identifier, request, digest, receipt):
        self.db.execute("INSERT INTO opora_execution_results VALUES(?,?,?,?,?,?)",
                        (*self.scope, identifier, request, digest, json.dumps(receipt, ensure_ascii=False)))

    def history(self, node=None):
        condition = " AND node_id=?" if node is not None else ""
        parameters = (*self.scope, node) if node is not None else self.scope
        rows = self.db.execute("SELECT owner,record FROM opora_executions WHERE project_id=? AND workspace_id=?"
                               + condition + " ORDER BY rowid DESC LIMIT 100", parameters).fetchall()
        return [json.loads(row[1]) | {"owner": row[0]} for row in rows]

    def receipts(self, identifier):
        self.read(identifier)
        rows = self.db.execute("SELECT record FROM opora_execution_results WHERE project_id=? AND workspace_id=?"
                               " AND execution_id=? ORDER BY rowid", (*self.scope, identifier)).fetchall()
        return [json.loads(row[0]) for row in rows]
