"""V3 native plan compilation; the same canvas builder owns all card semantics."""
from copy import deepcopy

from backend.canvas.architecture_graph import split
from backend.canvas.canvas_plan import _check_content
from backend.canvas.canvas_plan_build import build as build_canvas
from backend.canvas.canvas_plan_fields import stable_identities
from backend.canvas.graph import digest, validate_graph
from backend.canvas.opora_graph_build import NODE_KEYS, place, semantic
from backend.canvas.opora_graph_change_architecture import adoption
from backend.canvas.opora_graph_change_diff import changes, preconditions
from backend.canvas.opora_graph_change_plan import EDIT_KEYS, apply, normalize, validate_targets
from backend.editor.agent_memory.desktop_v3_state import check_node_branches, validate_state

CONTENT_FIELDS = {"text", "blocks", "rules", "agentRole", "criteria", "downloadsUrl", "fragmentRef",
                  "briefGroup", "briefDiscipline"}
PLAN_KEYS = {"nodes", "edges", "extend", "adoptArchitectureContext", "draftVersion", "researchSource", *EDIT_KEYS}


def required(plan):
    return isinstance(plan, dict) and (plan.get("draftVersion") == 3 or "extend" in plan
        or any(isinstance(node, dict) and set(node) & CONTENT_FIELDS for node in plan.get("nodes", [])))


def normalize_complete(raw):
    if (not isinstance(raw, dict) or not set(raw) <= PLAN_KEYS or type(raw.get("draftVersion", 3)) is not int
            or raw.get("draftVersion", 3) != 3):
        raise ValueError("Invalid complete graph plan fields/version.")
    plan = {key: deepcopy(raw.get(key, [])) for key in sorted(EDIT_KEYS | {"nodes", "edges", "extend"})}
    if any(not isinstance(value, list) for value in plan.values()) or not any(plan.values()):
        raise ValueError("Complete graph plan requires nonempty operation lists.")
    if type(raw.get("adoptArchitectureContext", False)) is not bool:
        raise ValueError("Architecture context adoption must be explicit.")
    plan["adoptArchitectureContext"] = raw.get("adoptArchitectureContext", False)
    if "researchSource" in raw:
        from backend.canvas.research_plan_source import shape
        shape(raw["researchSource"])
        plan["researchSource"] = deepcopy(raw["researchSource"])
    for node in plan["nodes"]:
        if not isinstance(node, dict) or node.get("kind") not in ("node", "sector", "area") or not set(node) <= NODE_KEYS | CONTENT_FIELDS:
            raise ValueError("Unsupported complete graph addition fields or kind.")
    structural(plan)  # Reuse native graph-edit shape/reference rules.
    return plan


def structural(plan):
    result = {key: deepcopy(plan[key]) for key in EDIT_KEYS}
    result.update(nodes=[{key: value for key, value in node.items() if key in NODE_KEYS} for node in plan["nodes"]],
                  edges=deepcopy(plan["edges"]), adoptArchitectureContext=plan["adoptArchitectureContext"])
    if any(result[key] for key in EDIT_KEYS | {"nodes", "edges"}) or result["adoptArchitectureContext"]:
        return normalize(result)
    return result  # Content-only extensions have no structural operation.


def compile_plan(plan, accepted, working, state, seed, *, identities=None, observed=None):
    patch = structural(plan)
    dependency, architecture = adoption(accepted, working, patch["adoptArchitectureContext"])
    validate_targets(dependency, working, patch)
    batch = {key: plan[key] for key in ("nodes", "edges", "extend")}
    built = []
    for graph in (dependency, working):
        base = apply(graph, patch)
        with stable_identities(seed, identities, observed):
            compiled = build_canvas(batch, base, state) if any(batch.values()) else None
        if compiled is None:
            from backend.canvas.canvas_plan_build import Built
            compiled = Built(base, state)
        validate_graph(compiled.new_graph())
        place({"nodes": compiled.nodes, "edges": compiled.edges}, compiled.graph, compiled.inside, compiled.positions)
        result = compiled.new_graph()
        validate_graph(result)
        if split(graph)[0] != split(result)[0]:
            raise ValueError("Complete proposals cannot mutate shared architecture.")
        built.append(compiled)
    approved, result = (item.new_graph() for item in built)
    if built[0].state != built[1].state or built[0].refs != built[1].refs:
        raise ValueError("Accepted and working content targets differ.")
    actual = built[1]
    additions = {"nodes": deepcopy(actual.nodes), "edges": deepcopy(actual.edges)}
    # Include graph fields changed by extend in the existing human review triples.
    review_patch = deepcopy(patch)
    indexed = {item["id"]: item for item in working["nodes"]}
    explicit = {item["id"]: item for item in review_patch["updateNodes"]}
    for node in actual.graph["nodes"]:
        old = indexed.get(node["id"])
        if old:
            fields = {key: node.get(key) for key in old.keys() | node.keys() if old.get(key) != node.get(key)}
            if fields:
                explicit.setdefault(node["id"], {"id": node["id"], "fields": {}})["fields"].update(fields)
    review_patch["updateNodes"] = list(explicit.values())
    review = changes(accepted, working, approved, result, review_patch, additions)
    review["architectureContext"] = architecture
    conditions = {}
    extended = {item["node"][1:] for item in plan["extend"]}
    for name, graph in (("accepted", accepted), ("working", working)):
        conditions[name] = preconditions(graph, review_patch, additions, actual.inside)
        conditions[name]["extendedNodes"] = {node["id"]: semantic(node) for node in graph["nodes"] if node["id"] in extended}
    return actual, {"plan": deepcopy(plan), "acceptedGraph": deepcopy(accepted), "baseGraph": deepcopy(working),
        "resultGraph": result, "acceptedResultGraph": approved, "additions": additions,
        "refs": actual.refs, "blocks": actual.blocks, "inside": actual.inside, "positions": actual.positions,
        "changes": review, "preconditions": conditions}


def validate_content(project, workspace, built):
    _check_content(project, workspace, built)
    validate_state(built.state)
    check_node_branches(built.state, {node["id"] for node in built.new_graph()["nodes"]})
    return digest(built.state)
