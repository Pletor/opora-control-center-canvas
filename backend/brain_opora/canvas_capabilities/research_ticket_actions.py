"""Native feedback provenance and holder checks remain authoritative for research ticket bridges."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.brain_opora.determinism import ticket
from backend.canvas.payload_errors import NextStep
from backend.editor.research import model, ticket_bridge
from backend.editor.research import service as research

CONTRACTS = {
    "research_ticket_routes.branch": contract(("ticketId", "feedbackId"), effect="research", replay=True,
        cas="Native immutable feedback/session/execution provenance and deterministic branch identity"),
    "research_ticket_routes.answer": contract(("ticketId", "feedbackId", "cardId", "revision", "text"), effect="ticket", replay=True,
        cas="Pinned research revision, resolves evidence, original holder and single feedback answer"),
}
for _contract in CONTRACTS.values():
    _contract["test"] = "backend/api/brain_opora/test_canvas_capability_research_tickets.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    payload = {"project": project, "workspace": workspace, **data}
    branch_id = ticket_bridge.branch_id(project, workspace, data["ticketId"], data["feedbackId"])

    def snapshot():
        found = ticket.get(service, project, data["ticketId"])
        if found["workspaceId"] != workspace:
            model.fail("Ticket belongs to another workspace.", 403, "gate_scope")
        try:
            branch = research.detail(service, project, workspace, branch_id, 1)["card"]
        except model.GateError as error:
            if error.code != "research_not_found":
                raise
            branch = None
        return {"ticket": found, "branch": branch}

    def verify(before, after, result):
        if capability.endswith(".branch"):
            valid = after["branch"] == result["card"] and before["ticket"] == after["ticket"]
        else:
            actual = next((row for row in after["ticket"]["feedback"] if row["feedbackId"] == data["feedbackId"]), None)
            # Native answer returns a compact feedback projection; a native replay returns its full record.
            valid = (actual is not None and all(actual.get(key) == value for key, value in result["feedback"].items())
                     and actual["answer"] is not None and bool(actual["answeredAt"])
                     and result["sessionId"] == actual["sessionId"]
                     and result["ticket"]["status"] == after["ticket"]["status"]
                     and before["branch"] == after["branch"])
        if not valid:
            raise NextStep("Native research ticket readback differs from the operation result.",
                           code="operation_incomplete", hint="Inspect the original ticket feedback and research branch; do not repeat blindly.")

    operation = ticket_bridge.open_branch if capability.endswith(".branch") else ticket_bridge.answer
    return run(service, project, workspace, session, capability, data, request_id,
               snapshot=snapshot, action=lambda: operation(service, payload, "agent", session["worker_name"]), verify=verify)
