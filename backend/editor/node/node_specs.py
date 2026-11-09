import json
from datetime import UTC, datetime

EMPTY_FIELDS = {"goal": "", "non_goals": "", "acceptance": ""}


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {
        "project",
        "workspace",
        "node",
        "expected_revision",
        "fields",
    }:
        raise ValueError("Neplatný formát zadání.")
    revision = payload["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("Neplatná očekávaná revize.")
    fields = payload["fields"]
    limits = {"goal": 4000, "non_goals": 8000, "acceptance": 12000}
    # `steps` is the optional versioned plan (docs/oporahub-plan-steps.md); older specs omit it.
    if not isinstance(fields, dict) or not set(limits) <= set(fields) <= {*limits, "steps", "harness", "affectedNodeIds"}:
        raise ValueError("Zadání vyžaduje cíl, omezení a podmínky dokončení.")
    for key, limit in limits.items():
        if not isinstance(fields[key], str) or len(fields[key]) > limit or "\0" in fields[key]:
            raise ValueError("Neplatný text nebo překročený limit zadání.")
    if "steps" in fields:
        from backend.canvas.opora_plan_steps import validate_steps

        validate_steps(fields["steps"])
    if "affectedNodeIds" in fields:
        from backend.canvas.execution_write_set import affected_ids
        affected_ids(fields)
        if payload["node"] in fields["affectedNodeIds"]:
            raise ValueError("A task cannot list itself as an affected element.")
    if "harness" in fields:
        from backend.library.harness_kit import validate_kit

        validate_kit(fields["harness"])


class NodeSpecStore:
    def __init__(self, canvas):
        self.canvas = canvas

    def read(self, scope):
        row = self.canvas.db_for(scope[0]).execute(
            "SELECT revision,fields,saved_at FROM node_spec_revisions WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY revision DESC LIMIT 1",
            scope,
        ).fetchone()
        if row is None:
            return {"revision": 0, "fields": dict(EMPTY_FIELDS), "saved_at": None}
        return {
            "revision": row["revision"],
            "fields": json.loads(row["fields"]),
            "saved_at": row["saved_at"],
        }

    def save(self, scope, expected_revision, fields):
        db = self.canvas.db_for(scope[0])
        with self.canvas.lock_for(scope[0]), db:
            db.execute("BEGIN IMMEDIATE")
            return self.save_in_transaction(scope, expected_revision, fields)

    def save_in_transaction(self, scope, expected_revision, fields):
        """Append within a caller-owned transaction; scope already resolves document ownership.

        The caller holds the project lock and owns commit/rollback, allowing several
        specifications and their accepted plan reference to change atomically.
        """
        db = self.canvas.db_for(scope[0])
        if not self.canvas.lock_for(scope[0])._is_owned() or not db.in_transaction:
            raise RuntimeError("Specification write requires a locked caller transaction.")
        validate_payload({"project": scope[0], "workspace": scope[1], "node": scope[2],
                          "expected_revision": expected_revision, "fields": fields})
        current = self.read(scope)
        if current["revision"] != expected_revision:
            raise ValueError(
                "Konflikt: zadání se změnilo v jiném okně. Rozepsaný text zůstal zachován."
            )
        revision = current["revision"] + 1
        saved_at = datetime.now(UTC).isoformat()
        db.execute(
            "INSERT INTO node_spec_revisions VALUES(?,?,?,?,?,?)",
            (*scope, revision, json.dumps(fields, ensure_ascii=False), saved_at),
        )
        return {"revision": revision, "fields": fields, "saved_at": saved_at}
