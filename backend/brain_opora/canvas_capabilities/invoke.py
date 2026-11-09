"""Named native adapters, without arbitrary HTTP paths or caller-controlled authors."""
from urllib.parse import urlencode
from backend.brain_opora.canvas_capabilities import knowledge_actions, storyboard_actions, content_actions
from backend.brain_opora.canvas_capabilities import brief_actions, research_continuation_actions
from backend.brain_opora.canvas_capabilities import design_reads, research_ticket_actions, flow_actions, lease_actions, research_review_actions, desktop_work_actions, source_realization_action, desktop_review_actions, changeset_review_actions, working_graph_actions

from backend.brain_opora.canvas_capabilities.catalog import describe
from backend.canvas.canvas_index import DEFAULT_LIMIT, build_index, search
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_step_results import plan_view
from backend.canvas.payload_errors import InvalidPayload, NextStep
from backend.brain_opora.canvas_capabilities import library_actions
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.brain_opora.canvas_capabilities import canvas_reads, readiness_reads, site_reads, research_reads, proposal_writes, vault_reads, flow_reads, flow_inspect, library_reads, draft_writes, research_actions, changeset_actions, desktop_reads, research_tasks, site_actions, flow_drafts, desktop_evidence_reads, desktop_packet_actions, node_materials, version_actions, layout_actions, revise_actions, desktop_memory_actions


def invoke(service, project, workspace, session, capability, data, request_id=None):
    item = describe(capability)
    if not item["implemented"]:
        raise NextStep("This audited operation has no verified adapter yet.", code="capability_unimplemented",
                       hint="Inspect discover/describe; this is not reported as completed coverage.")
    spec = item["adapter"]
    if not isinstance(data, dict) or set(spec["required"]) - data.keys() or data.keys() - set(spec["required"] + spec["optional"]):
        raise InvalidPayload("Invalid fields for this capability.", field="input", expected=spec)
    if spec["replay"] and not request_id:
        raise InvalidPayload("A stable requestId is required for this write.", field="requestId")
    if not spec["replay"] and request_id is not None:
        raise InvalidPayload("This read/preparation does not consume requestId.", field="requestId")
    if spec["effect"] in ("read", "human-decision"):
        for key, value in data.items():
            kind = spec["types"].get(key, "integer" if key == "limit" else "string")
            valid = (type(value) is int if kind == "integer" else type(value) is bool if kind == "boolean"
                     else isinstance(value, dict) if kind == "object" else True if kind == "json"
                     else isinstance(value, str) and len(value) <= 10000)
            if not valid:
                raise InvalidPayload("Invalid read parameter type.", field=key, expected=kind)
    for module in (knowledge_actions, storyboard_actions, content_actions):
        if capability in module.CONTRACTS:
            return module.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in research_continuation_actions.CONTRACTS:
        return research_continuation_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in brief_actions.CONTRACTS:
        return brief_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in site_reads.CONTRACTS:
        return {"state": "read", "result": site_reads.read(service, project, capability, data)}
    if capability in research_reads.CONTRACTS:
        return {"state": "read", "result": research_reads.read(service, project, workspace, capability, data)}
    if capability in proposal_writes.CONTRACTS:
        if capability != "canvas_routes.canvas_plan" and (not isinstance(data["node"], str) or not data["node"]):
            raise InvalidPayload("node must be a nonempty native node ID.", field="node")
        return proposal_writes.prepare(service, project, workspace, session, capability, data, request_id)
    if capability in vault_reads.CONTRACTS:
        from starlette.responses import Response
        result = vault_reads.read(service, project, workspace, capability, data)
        return result if isinstance(result, Response) else {"state": "read", "result": result}
    if capability in flow_reads.CONTRACTS:
        return {"state": "read", "result": flow_reads.read(service, project, capability, data)}
    if capability in flow_inspect.CONTRACTS:
        return {"state": "read", "result": flow_inspect.read(capability, data)}
    if capability in library_reads.CONTRACTS:
        return {"state": "read", "result": library_reads.read(service, project, capability, data)}
    if capability in library_actions.CONTRACTS:
        return library_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in draft_writes.CONTRACTS:
        return draft_writes.write(service, project, workspace, session, capability, data, request_id)
    if capability in research_actions.CONTRACTS:
        return research_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in changeset_actions.CONTRACTS:
        return changeset_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in desktop_reads.CONTRACTS:
        from starlette.responses import Response
        result = desktop_reads.read(service, project, workspace, capability, data)
        return result if isinstance(result, Response) else {"state": "read", "result": result}
    if capability in research_tasks.CONTRACTS:
        return research_tasks.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in site_actions.CONTRACTS:
        return site_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in flow_drafts.CONTRACTS:
        return flow_drafts.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in desktop_evidence_reads.CONTRACTS:
        return {"state": "read", "result": desktop_evidence_reads.read(service, project, workspace, capability, data)}
    if capability in desktop_packet_actions.CONTRACTS:
        return desktop_packet_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in node_materials.CONTRACTS:
        return node_materials.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in version_actions.CONTRACTS:
        return version_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in layout_actions.CONTRACTS:
        return layout_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in revise_actions.CONTRACTS:
        return revise_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in desktop_memory_actions.CONTRACTS:
        return desktop_memory_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in design_reads.CONTRACTS:
        return {'state': 'read', 'result': design_reads.read(service, project, capability, data)}
    if capability in research_ticket_actions.CONTRACTS:
        return research_ticket_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in flow_actions.CONTRACTS:
        return flow_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in lease_actions.CONTRACTS:
        return lease_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in research_review_actions.CONTRACTS:
        return research_review_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in desktop_work_actions.CONTRACTS:
        return desktop_work_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in source_realization_action.CONTRACTS:
        return source_realization_action.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in desktop_review_actions.CONTRACTS:
        return desktop_review_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in changeset_review_actions.CONTRACTS:
        return changeset_review_actions.invoke(service, project, workspace, session, capability, data, request_id)
    if capability in working_graph_actions.CONTRACTS:
        return working_graph_actions.invoke(service, project, workspace, session, capability, data, request_id)
    native = OporaGraphProposals(service)
    if capability in canvas_reads.CONTRACTS:
        return {"state": "read", "result": canvas_reads.read(service, project, workspace, capability, data)}
    if capability in readiness_reads.CONTRACTS:
        return {"state": "read", "result": readiness_reads.read(service, project, workspace, capability)}
    if capability.startswith("session_view."):
        from backend.brain_opora.canvas_capabilities import session_view
        return session_view.read(service, project, workspace, session) if capability.endswith("read") else session_view.update(
            service, project, workspace, session, data, request_id)
    if capability == "canvas_routes.view":
        result = service.view(project, workspace)
    elif capability == "canvas_routes.canvas_index":
        q, limit = data.get("q", ""), data.get("limit", DEFAULT_LIMIT)
        if not isinstance(q, str) or type(limit) is not int:
            raise InvalidPayload("q must be text and limit an integer.", field="input")
        with service.reading(project):
            result = search(build_index(service.view(project, workspace)["graph"],
                DesktopV3State(service).read(project, workspace)["state"]), q, limit)
    elif capability in ("node_routes.node_text", "node_routes.node_spec"):
        if capability.endswith("node_text"):
            result = service.texts.access(project, workspace, data["node"])
        else:
            result = service.node_spec(project, workspace, data["node"])
            if result.get("available"):
                result = plan_view(service, project, workspace, data["node"], result)
    elif capability == "opora_graph_routes.context":
        result = native.context(project, workspace)
    elif capability == "opora_graph_routes.history":
        result = native.list(project, workspace)
    elif capability in ("opora_graph_routes.read", "opora_graph_routes.accept"):
        result = native.read(project, workspace, data["identifier"])
        if capability.endswith("accept"):
            return {"state": "awaiting_human", "applied": False, "proposal": result,
                    "url": "/?" + urlencode({"project": project, "workspace": workspace, "screen": "canvas",
                                               "environment": "hub", "ohGraph": result["id"]})}
    elif capability == "opora_graph_routes.create":
        return proposal_writes.persist(service, project, workspace, session, data, request_id)
    else:
        raise RuntimeError("Catalog adapter has no explicit handler.")
    return {"state": "read", "result": result}
