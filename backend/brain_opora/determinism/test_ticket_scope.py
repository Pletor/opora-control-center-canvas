from backend.canvas.test_opora_changesets import service, baseline
from backend.brain_opora.determinism.ticket_scope import project_scopes
from database.repositories.opora_executions import Executions


def test_ticket_scope_is_read_projection_and_execution_pin_wins(service):
    fields={"goal":"Update login","non_goals":"","acceptance":"Tenant scenario","affectedNodeIds":["b"]}
    service.specs.save(("draft","draft","a"),0,fields)
    accepted=baseline(service)
    db=service.db_for("draft")
    ticket={"ticketId":"task","machine":{"cardId":"a","executionId":None}}
    before=project_scopes(db,"draft","draft",[ticket])[0]
    assert before["machine"]["affectedNodeIds"]==["b"]
    assert before["machine"]["affectedScopeSource"]["kind"]=="accepted_spec"
    assert "affectedNodeIds" not in ticket["machine"]
    with db:
        Executions(db,"draft","draft").insert({"executionId":"run","nodeId":"a","acceptedRevision":accepted["id"],"assignment":{"affectedElements":[{"nodeId":"page"}] }},"agent:worker","req","digest")
    frozen=project_scopes(db,"draft","draft",[{**ticket,"machine":{"cardId":"a","executionId":"run"}}])[0]
    assert frozen["machine"]["affectedNodeIds"]==["page"]
    assert frozen["machine"]["affectedScopeSource"]["kind"]=="execution"
    missing=project_scopes(db,"draft","draft",[{**ticket,"machine":{"cardId":"a","executionId":"missing"}}])[0]
    assert missing["machine"]["affectedNodeIds"]==[]
