"""Observe native research completion before planning; never write or guess original output."""
import json

from backend.canvas.graph import digest
from backend.editor.brief_vault.brief_vault_details import empty_research, validate_research
from backend.editor.research import model

OUTPUT_FIELDS = ("verdict", "confidence", "approach", "evidence")


def expected(value):
    model.shape(value, set(OUTPUT_FIELDS) | {"status"})
    if value["status"] != "done":
        model.fail("Research finalization must describe a completed native research output.")
    try:
        validate_research({**empty_research("Completion input is pinned separately"), **value})
    except ValueError as error:
        model.fail(str(error))
    return value


def output_digest(research):
    return digest({key: research.get(key) for key in OUTPUT_FIELDS})


def validate_output(db, project, workspace, pin):
    rows = db.execute("SELECT fields FROM brief_fragment_details WHERE project_id=? AND workspace_id=? "
                      "AND fragment_id=? AND revision>=? ORDER BY revision",
                      (project, workspace, pin["id"], pin["detailsRevision"])).fetchall()
    if not rows or any(output_digest(json.loads(row[0]).get("research", {})) != pin["digest"] for row in rows):
        raise ValueError("Original research output changed; affected work needs reassessment.")


def observe(db, project, workspace, item):
    """Caller persists receipt in its transaction; missing completion never wakes the LLM."""
    intended = item.get("finalization")
    if intended is None:
        return True  # Explicit compatibility: older receipts retain their recorded coverage.
    evidence = item["evidence"]
    from backend.editor.research.execution_evidence import validate
    validate(db, project, workspace, {"records": [{"evidence": evidence}]})
    if evidence.get("originalOutput"):
        return True
    rows = db.execute("SELECT revision,fields FROM brief_fragment_details WHERE project_id=? AND workspace_id=? "
                      "AND fragment_id=? AND revision>? ORDER BY revision",
                      (project, workspace, item["sourceFragmentId"], evidence["originalInput"]["detailsRevision"]))
    for revision, raw in rows:
        research = json.loads(raw).get("research", {})
        if research.get("status") != "done":
            continue
        if any(research.get(key) != value for key, value in intended.items()):
            raise ValueError("Native research completion differs from the imported finalization intent.")
        pin = {"id": item["sourceFragmentId"], "detailsRevision": revision, "digest": output_digest(research)}
        validate_output(db, project, workspace, pin)
        evidence["originalOutput"] = pin
        evidence["originalSourceCoverage"] = "semantic-input-and-observed-completed-output"
        item.update(status="pending", error=None)
        return True
    item.update(status="awaiting_finalization", error="Awaiting the exact native research completion saved in the import artifact.")
    return False
