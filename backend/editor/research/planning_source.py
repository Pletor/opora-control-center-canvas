"""Typed source pins on a native proposal; validation does not approve research claims."""
import json
from backend.editor.research import model

FIELDS = {"continuationId", "researchId", "researchRevision", "sourceFragmentId", "sourceRevision"}


def shape(source):
    model.shape(source, FIELDS)
    for field in ("continuationId", "researchId", "sourceFragmentId"):
        model.identifier(source[field])
    for field in ("researchRevision", "sourceRevision"):
        if type(source[field]) is not int or source[field] < 1:
            model.fail(field + " must be a positive integer.")
    return source


def pins(item):
    return {"continuationId": item["id"], **{key: item[key] for key in FIELDS - {"continuationId"}}}


def validate_source(canvas, project, workspace, source):
    shape(source)
    with canvas.reading(project):
        db = canvas.db_for(project)
        row = db.execute("SELECT payload FROM research_continuations WHERE project_id=? AND workspace_id=? AND id=?",
                         (project, workspace, source["continuationId"])).fetchone()
        if row is None or pins(json.loads(row[0])) != source:
            model.fail("Proposal research source does not match the scoped continuation.", 409, "research_source_conflict")
        current = db.execute("SELECT MAX(revision) FROM research_card_revisions WHERE project_id=? AND workspace_id=? AND id=?",
                             (project, workspace, source["researchId"])).fetchone()[0]
        if current != source["researchRevision"]:
            model.fail("Research source revision changed.", 409, "research_source_conflict")
        receipt = json.loads(row[0])
        if receipt.get("finalization") is not None and not receipt.get("evidence", {}).get("originalOutput"):
            model.fail("Native research completion has not been observed; planning must wait.", 409, "research_awaiting_finalization")
        if receipt.get("evidence") is not None:
            from backend.editor.research.execution_evidence import validate
            try:
                validate(db, project, workspace, {"records": [{"evidence": receipt["evidence"]}]})
            except ValueError as error:
                model.fail(str(error), 409, "research_source_conflict")
    return source
