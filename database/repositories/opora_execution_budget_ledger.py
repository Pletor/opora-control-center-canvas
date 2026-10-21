"""Immutable family allocation ledger; mixed into the scoped policy repository."""

import json

from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_execution_budget_ledger_validation import ledger
from backend.canvas.opora_hub_store import canonical, content_id


class BudgetLedger:
    def family_id(self, accepted):
        identifier(accepted)
        return content_id(
            {
                "project": self.scope[0],
                "workspace": self.scope[1],
                "nodeId": self.node,
                "acceptedRevision": accepted,
            }
        )

    def events(self, accepted):
        fid = self.family_id(accepted)
        rows = self.db.execute(
            "SELECT id,sequence,kind,execution_id,content FROM opora_execution_budget_ledger WHERE project_id=? AND workspace_id=? AND family_id=? ORDER BY sequence",
            (*self.scope, fid),
        ).fetchall()
        records = []
        for record_id, sequence, kind, execution, raw in rows:
            try:
                record = json.loads(raw)
                ledger(record, records)
                if record['kind']=='allocation' and self.read_policy(record['policyHead'])!=record['policySnapshot']:
                    raise ValueError('Stored allocation policy snapshot mismatch.')
                self.integrity(record, record_id)
                if (
                    record["familyId"] != fid
                    or record["acceptedRevision"] != accepted
                    or record["sequence"] != len(records) + 1
                    or sequence != record["sequence"]
                    or kind != record["kind"]
                    or execution != record["executionId"]
                    or record["parentId"] != (records[-1]["id"] if records else None)
                ):
                    raise ValueError("Budget ledger sequence integrity mismatch.")
                records.append(record)
            except (KeyError, TypeError, AttributeError) as error:
                raise ValueError("Malformed stored budget ledger.") from error
        return records

    def append(self, accepted, content):
        self.tx()
        previous = self.events(accepted)
        value = {
            "schemaVersion": 1,
            "project": self.scope[0],
            "workspace": self.scope[1],
            "nodeId": self.node,
            "acceptedRevision": accepted,
            "familyId": self.family_id(accepted),
            "sequence": len(previous) + 1,
            "parentId": previous[-1]["id"] if previous else None,
            **content,
        }
        record = {**value, "id": content_id(value)}
        ledger(record, previous)
        self.db.execute(
            "INSERT INTO opora_execution_budget_ledger VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                *self.scope,
                self.node,
                accepted,
                record["familyId"],
                record["sequence"],
                record["id"],
                record["kind"],
                record["executionId"],
                canonical(record),
            ),
        )
        return record

    def family(self, accepted, require_complete=True):
        events = self.events(accepted)
        if require_complete:
            from database.repositories.opora_execution_budget_integrity import family_integrity

            family_integrity(self, accepted, events)
        reported = False
        for event in events:
            row = self.db.execute(
                "SELECT 1 FROM opora_execution_results WHERE project_id=? AND workspace_id=? AND execution_id=? LIMIT 1",
                (*self.scope, event["executionId"]),
            ).fetchone()
            execution = self.db.execute(
                "SELECT record FROM opora_executions WHERE project_id=? AND workspace_id=? AND id=?",
                (*self.scope, event["executionId"]),
            ).fetchone()
            # Losing a receipt must never move a durably reported family back to retries.
            durably_reported = execution and json.loads(execution[0]).get("state") == "reported"
            reported = reported or bool(row) or bool(durably_reported) or event.get("legacyReported", False)
        return {
            "id": self.family_id(accepted),
            "acceptedRevision": accepted,
            "attempts": len(events),
            "repairRounds": sum(event["runKind"] == "repair" for event in events),
            "lastExecutionId": events[-1]["executionId"] if events else None,
            "hasReported": reported,
        }
