"""Reuse native receipt history to prevent reassignment of a paired evaluation identity."""
import json

from backend.library.harness_paired_results import validate_report


def validate_result(result, record, repo):
    value = validate_report(result, record)
    if value is None:
        return
    rows = repo.db.execute(
        "SELECT record FROM opora_execution_results WHERE project_id=? AND workspace_id=?"
        " AND execution_id=? AND json_type(record,'$.result.harnessPairedEvaluation') IS NOT NULL"
        " ORDER BY rowid DESC LIMIT 129", (*repo.scope, record["executionId"])).fetchall()
    if len(rows) > 128:
        raise ValueError("Harness paired evaluation receipt limit reached for this execution.")
    for row in rows:
        try:
            prior = validate_report(json.loads(row[0])["result"], record)
        except (ValueError, KeyError, TypeError):
            continue  # Unvalidated historical claims cannot establish a paired identity.
        if prior and prior["evaluationId"] == value["evaluationId"] and prior != value:
            raise ValueError("Harness paired evaluation identity was already used for different evidence.")
