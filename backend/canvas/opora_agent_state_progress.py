"""Pin-checked card progress, projected from accepted specs and existing milestone receipts."""
from backend.brain_opora.determinism import milestone_evidence
from database.repositories.intake_milestones import IntakeMilestones


def attach(db, project, workspace, entries, documents, accepted):
    by_node = {doc["nodeId"]: doc for doc in documents}
    proof = {}
    for milestone in IntakeMilestones(db).proof_candidates(workspace):
        evidence = milestone_evidence.evaluate(db, project, workspace, milestone["criteria"])
        if evidence["verified"]:
            for criterion in milestone["criteria"]:
                for node in criterion["cards"]:
                    proof[node] = {**evidence, "milestoneId": milestone["id"],
                                   "milestoneAcceptance": "active" if milestone["status"] == "active" else "replaced",
                                   **({"milestoneReplacedBy": milestone["replacedBy"]} if milestone.get("replacedBy") else {})}
    result = []
    for entry in entries:
        fields = by_node.get(entry["nodeId"], {}).get("fields", {})
        design = bool(accepted and fields.get("goal", "").strip() and fields.get("acceptance", "").strip())
        result.append({**entry, "progressEvidence": {"acceptedRevision": accepted, "designAccepted": design,
                       **({"verification": proof[entry["nodeId"]]} if entry["nodeId"] in proof else {})}})
    return result
