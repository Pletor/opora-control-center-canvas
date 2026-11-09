"""Read native vault records after a handler; no parallel operation semantics."""
from backend.canvas.payload_errors import NextStep
from backend.editor.brief_vault.brief_vault_details import feedback_rows, latest_details
from backend.editor.brief_vault.brief_vault_gate_rules import gate_state, summary
from backend.editor.brief_vault.brief_vault_lessons import public as public_lesson
from backend.editor.brief_vault.brief_vault_model import effective_disciplines, latest_rows
from backend.editor.brief_vault.brief_vault_proposals import public_proposal


def require_equal(actual, expected):
    if actual != expected:
        raise NextStep("Native vault result differs from stored records.", code="operation_incomplete",
                       hint="Read the pending operation and reconcile native records before retrying.")


def verify_details(service, project, workspace, result):
    db = service.db_for(project)
    fragment = result.get("fragment")
    if fragment:
        fields = latest_details(db, project, workspace, [fragment["id"]]).get(fragment["id"], {}).get("fields", {})
        if "details" in result:
            require_equal(fields, result["details"])
        if "duel" in result:
            require_equal(fields.get("duel"), result["duel"])
        if "point" in result:
            points = fields.get("vision", {}).get("points", [])
            require_equal(result["point"] in points, True)
        if "gates" in result:
            rows = latest_rows(db, project, workspace)
            discipline = effective_disciplines(rows).get(fragment["id"])
            actual = summary(gate_state(rows[fragment["id"]], discipline))
            require_equal(actual, {key: result[key] for key in actual})
    if "feedback" in result:
        item = result["feedback"]
        actual = next((row for row in feedback_rows(db, project, workspace, [item["fragmentId"]]) if row["id"] == item["id"]), None)
        require_equal(actual, item)
    if "lesson" in result:
        item = result["lesson"]
        row = db.execute("SELECT * FROM brief_lessons WHERE project_id=? AND workspace_id=? AND lesson_id=? AND revision=?",
                         (project, workspace, item["id"], item["revision"])).fetchone()
        actual = public_lesson(row) if row else {}
        # Time decay is derived on read; immutable lesson fields must all match.
        require_equal({key: value for key, value in actual.items() if key != "effectiveWeight"},
                      {key: value for key, value in item.items() if key != "effectiveWeight"})
    for key in ("proposal", "rejected"):
        if key not in result:
            continue
        item = result[key]
        row = db.execute("SELECT * FROM brief_gate_proposals WHERE project_id=? AND workspace_id=? AND id=?",
                         (project, workspace, item["id"])).fetchone()
        actual = public_proposal(row) if row else {}
        require_equal(actual, {name: value for name, value in item.items() if name not in ("status", "rejection")})
        if key == "rejected":
            rejection = db.execute("SELECT * FROM brief_gate_proposal_rejections WHERE project_id=? AND workspace_id=? AND proposal_id=?",
                                   (project, workspace, item["id"])).fetchone()
            require_equal({name: rejection[name] for name in ("id", "note", "by", "actor", "at")} if rejection else None, item["rejection"])
    if "idea" in result:
        from backend.editor.brief_vault.brief_vault import BriefVault
        item = result["idea"]
        stored = BriefVault(service).state.current(project, workspace)
        require_equal(stored["revision"], result["stateRevision"])
        ideas = stored["state"]["nodes"][item["nodeId"]]["ideas"]
        found = next((idea for idea in ideas if idea["id"] == item["ideaId"]), {})
        require_equal(found.get("fragmentId"), item["fragmentId"])
