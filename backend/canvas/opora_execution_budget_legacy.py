"""Import every matching pre-policy execution once without inventing runtime limits."""

import json
import re

from backend.canvas.graph import digest
from backend.canvas.opora_execution_input_version import context_version
from backend.canvas.opora_execution_budget_validation import execution_id, finite
from backend.canvas.opora_hub_store import content_id
from backend.canvas.opora_review_policy_validation import timestamp


def seed_legacy(repo, accepted):
    repo.tx()
    existing = {item["executionId"] for item in repo.events(accepted)}
    family = repo.family(accepted, require_complete=False)
    reported = family["hasReported"]
    rows = repo.db.execute(
        "SELECT id,project_id,workspace_id,node_id,record FROM opora_executions WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY rowid",
        (*repo.scope, repo.node),
    ).fetchall()
    for identifier, pid, wid, node, raw in rows:
        try:
            value = json.loads(raw)
            if value["acceptedRevision"] != accepted:
                continue
            execution_id(identifier)
            if (
                (value["project"], value["workspace"], value["nodeId"], value["executionId"])
                != (pid, wid, node, identifier)
                or value["assignmentDigest"] != digest(value["assignment"])
                or value["assignment"]["acceptedRevision"] != accepted
                or type(value["epoch"]) is not int
                or value["epoch"] < 1
                or value["state"] not in ("running", "released", "reported", "cancelled")
                or not isinstance(value.get("token"), str)
                or re.fullmatch("[a-f0-9]{64}", value["token"]) is None
                or value["assignment"]["contextVersion"]
                != context_version(value["assignment"])
                or value["assignment"]["specification"]["scope"]
                != {"project": pid, "workspace": wid, "nodeId": node}
            ):
                raise ValueError("Legacy execution identity is invalid.")
            timestamp(value["createdAt"])
            finite(value["expiresAt"])
            if identifier in existing:
                continue
            run_kind = "repair" if reported else "initial" if not existing else "retry"
            is_reported = value["state"] == "reported" or bool(
                repo.db.execute(
                    "SELECT 1 FROM opora_execution_results WHERE execution_id=? LIMIT 1",
                    (identifier,),
                ).fetchone()
            )
            repo.append(
                accepted,
                {
                    "kind": "legacy-import",
                    "executionId": identifier,
                    "runKind": run_kind,
                    "legacyReported": is_reported,
                    "createdAt": value["createdAt"],
                    "legacyRecordDigest": content_id(value),
                },
            )
            existing.add(identifier)
            reported = reported or is_reported
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError(
                "Legacy execution history is malformed; budget enrollment is unavailable."
            ) from error
