"""Pure flow inspection reuses native request models, catalogs and graph validators."""
from fastapi import HTTPException
from pydantic import ValidationError, TypeAdapter
from backend.api.flow.flow_routes import Kind, GraphCheckIn, NodePortsIn, SimulateIn, _port_json
from backend.flow.graph_check import graph_errors, node_ports, FlowInvalid
from backend.flow.node_types import catalog
from backend.flow.simulate import simulate
from backend.brain_opora.canvas_capabilities.contracts import contract

CONTRACTS = {
    "flow_routes.node_type_list": contract(optional=("kind",)),
    "flow_routes.node_port_list": contract(("type",), ("kind", "params", "onError"), types={"params": "object"}),
    "flow_routes.graph_check": contract(("kind", "graph"), types={"graph": "json"}),
    "flow_routes.simulate_case": contract(("graph",), ("caseId", "case"), types={"graph": "object", "case": "object"}),
}


def read(capability, data):
    try:
        if capability == "flow_routes.node_type_list":
            kind = TypeAdapter(Kind).validate_python(data["kind"]) if "kind" in data else None
            return {"node_types": [{"type": t.type, "version": t.version, "trigger": t.trigger, "params": t.params,
                "category": t.category, "dynamicPorts": t.dynamic is not None, "layer": t.layer,
                "use": t.use, "avoid": t.avoid, "intents": list(t.intents), "accepts": list(t.accepts),
                "emits": t.emits or None, "ports": [_port_json(p) for p in t.ports]} for t in catalog(kind).values()]}
        if capability == "flow_routes.node_port_list":
            body = NodePortsIn.model_validate(data)
            node_type = catalog(body.kind).get(body.type)
            if node_type is None:
                raise HTTPException(404, "Unknown native node type.")
            node = {"params": body.params, "onError": body.onError}
            return {"type": body.type, "ports": [_port_json(p) for p in node_ports(node_type, node, body.kind)]}
        if capability == "flow_routes.graph_check":
            body = GraphCheckIn.model_validate(data)
            errors = graph_errors(body.graph, catalog(body.kind), body.kind)
            return {"ok": not errors, "errors": errors}
        if capability == "flow_routes.simulate_case":
            body = SimulateIn.model_validate(data)
            return simulate(body.graph, body.caseId, body.case)
    except (ValidationError, FlowInvalid) as error:
        raise HTTPException(422, str(error)) from error
    raise RuntimeError("Unknown finite flow inspection")
