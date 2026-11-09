"""Read-only task scope projection from one accepted spec or its frozen execution."""
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions


def project_scopes(db, project, workspace, tickets):
    changes = ChangesetRepository(db, project, workspace)
    head = changes.head()
    documents = {d["nodeId"]: d for d in changes.read(head)["documents"]} if head else {}
    result=[]
    for ticket in tickets:
        machine=ticket["machine"]
        execution=machine.get("executionId")
        ids=[]; source=None
        if execution:
            try:
                record=Executions(db,project,workspace).read(execution)
                ids=[item["nodeId"] for item in record["assignment"].get("affectedElements",[])]
                source={"kind":"execution", "executionId":execution, "acceptedRevision":record["acceptedRevision"]}
            except ValueError:
                pass  # Never substitute a newer spec for a missing historical run.
        else:
            fields=documents.get(machine.get("cardId"),{}).get("fields",{})
            ids=fields.get("affectedNodeIds",[])
            if ids:
                source={"kind":"accepted_spec", "acceptedRevision":head}
        result.append({**ticket,"machine":{**machine,"affectedNodeIds":list(dict.fromkeys(ids)),"affectedScopeSource":source}})
    return result
