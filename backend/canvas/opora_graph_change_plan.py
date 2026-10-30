"""Explicit graph patch input; no inferred deletion or working-graph adoption."""

from copy import deepcopy

from backend.canvas.graph import EDGE_CARRIES, valid_id
from backend.canvas.opora_graph_build import validate_plan
from backend.canvas.payload_errors import NextStep

FIELDS = {"name", "purpose", "parentId", "sourceRef", "x", "y", "size", "memberOf"}
EDIT_KEYS = {"updateNodes", "removeNodes", "updateEdges", "removeEdges"}
EDGE_UPDATE_KEYS = {"id", "source", "target", "port"}
# Úprava existujícího uzlu od srdce (docs/brain-heart-orchestrator.md §3): jen členství v oblasti (`member`).
# Přírůstky (`plan`) a odebrání (`unlink`, `prune`) jdou dál; ostatní pole uzlu a úpravy vazeb navrhuje člověk.
HEART_NODE_FIELDS = {"memberOf"}


class HeartEditRefused(NextStep):
    """Návrh grafu srdce mění víc než členství existujícího uzlu: HTTP 422 s `code` a `hint`."""

    status = 422


def heart_scope(plan):
    """Hranice návrhu grafu od srdce: `updateNodes` jen s polem `memberOf`, žádné `updateEdges`.
    Tvar plánu dál ověřuje `normalize`; tady jde jen o to, co srdce smí měnit."""
    if not isinstance(plan, dict):
        return
    hint = ("Srdce mění u existujícího uzlu jen členství v oblasti (memberOf, opora_heart.py member); jiné úpravy "
            "uzlů a vazeb navrhuje člověk v UI.")
    if plan.get("updateEdges"):
        raise HeartEditRefused("Srdce nesmí upravovat vazby (updateEdges).", code="heart_edit_scope", hint=hint)
    for item in plan.get("updateNodes") or []:
        fields = item.get("fields") if isinstance(item, dict) else None
        extra = sorted(set(fields) - HEART_NODE_FIELDS) if isinstance(fields, dict) else ["fields"]
        if extra:
            raise HeartEditRefused(f"Srdce u existujícího uzlu mění jen memberOf, ne {', '.join(extra)}.",
                                   code="heart_edit_scope", hint=hint)


def edge_update_fields(update):
    """Pole, která úprava vazby mění: zdroj, cíl a port vždy, druh toku `carries` jen když ho úprava uvádí
    (null ho odebere). Úprava bez `carries` dává stejná pole jako dřív, takže staré záznamy odvodí totéž."""
    return ("source", "target", "port", "carries") if "carries" in update else ("source", "target", "port")


def normalize(plan):
    if not isinstance(plan, dict) or not set(plan) <= EDIT_KEYS | {"nodes", "edges", "adoptArchitectureContext"}:
        raise ValueError("Invalid graph change plan fields.")
    result = {key: deepcopy(plan.get(key, [])) for key in sorted(EDIT_KEYS | {"nodes", "edges"})}
    if any(not isinstance(value, list) for value in result.values()):
        raise ValueError("Graph operations must be lists.")
    if type(plan.get("adoptArchitectureContext", False)) is not bool:
        raise ValueError("Architecture context adoption must be an explicit boolean.")
    if (not any(result.values()) and not plan.get("adoptArchitectureContext")) or sum(map(len, result.values())) > 6000:
        raise ValueError("Graph change operations are empty or exceed limits.")
    validate_plan({key: result[key] for key in ("nodes", "edges")})
    for key in ("updateNodes", "updateEdges"):
        for item in result[key]:
            allowed = ({"id", "fields"},) if key == "updateNodes" else (EDGE_UPDATE_KEYS, EDGE_UPDATE_KEYS | {"carries"})
            if not isinstance(item, dict) or set(item) not in allowed or not valid_id(item["id"]):
                raise ValueError("Invalid graph update fields or identity.")
            if key == "updateNodes":
                fields = item["fields"]
                if not isinstance(fields, dict) or not fields or not set(fields) <= FIELDS:
                    raise ValueError("Unsupported or empty node field patch.")
                if "parentId" in fields and fields["parentId"] is not None and not valid_id(fields["parentId"]):
                    raise ValueError("Parent references must be existing node identities.")
                if "memberOf" in fields and fields["memberOf"] is not None and not valid_id(fields["memberOf"]):
                    raise ValueError("Membership references must be existing area identities or null.")
            elif item["port"] != "next" or not all(valid_id(item[field]) for field in ("source", "target")):
                raise ValueError("Only plain next edge updates with existing references are supported.")
            elif "carries" in item and item["carries"] is not None and item["carries"] not in EDGE_CARRIES:
                raise ValueError("Unknown edge carries value.")
    for kind in ("Nodes", "Edges"):
        remove, update = result[f"remove{kind}"], result[f"update{kind}"]
        if any(not valid_id(item) for item in remove):
            raise ValueError("Invalid removal identity.")
        ids = [*remove, *(item["id"] for item in update)]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate or conflicting graph operations.")
    return {**result, "adoptArchitectureContext": plan.get("adoptArchitectureContext", False)}


def apply(graph, plan):
    result = deepcopy(graph)
    for kind in ("nodes", "edges"):
        suffix = kind.title()
        indexed = {item["id"]: item for item in result[kind]}
        for update in plan[f"update{suffix}"]:
            target = indexed.get(update["id"])
            if target is None:
                raise ValueError("Updated graph identity is absent from accepted or working context.")
            if kind == "nodes" and target["kind"] not in ("node", "sector", "area"):
                raise ValueError("Shared architecture and special nodes cannot be edited.")
            if kind == "edges" and target.get("port", "next") != "next":
                raise ValueError("Only plain next edges can be updated.")
            fields = update["fields"] if kind == "nodes" else {key: update[key] for key in edge_update_fields(update)}
            for key, value in fields.items():
                if kind == "edges" and key == "port" and target.get("port", "next") == value:
                    continue
                if key in ("sourceRef", "size", "memberOf", "carries") and value is None:
                    target.pop(key, None)
                else:
                    target[key] = deepcopy(value)
        removed = set(plan[f"remove{suffix}"])
        if kind == "edges" and any(item["id"] in removed and item.get("port", "next") != "next" for item in result[kind]):
            raise ValueError("Only plain next edges can be removed.")
        if kind == "nodes":
            if any(item["id"] in removed and item["kind"] not in ("node", "sector", "area") for item in result[kind]):
                raise ValueError("Shared architecture and special nodes cannot be removed.")
            missing = {item["id"] for item in result[kind] if item.get("parentId") in removed and item["id"] not in removed}
            if missing:
                raise ValueError(f"Explicit descendant removals required: {', '.join(sorted(missing))}")
        result[kind] = [item for item in result[kind] if item["id"] not in removed]
    removed = set(plan["removeNodes"])
    incident = {edge["id"] for edge in result["edges"] if edge["source"] in removed or edge["target"] in removed}
    if incident:
        raise ValueError(f"Explicit incident edge removals required: {', '.join(sorted(incident))}")
    return result


def validate_targets(accepted, working, plan):
    for kind in ("nodes", "edges"):
        ids = {item["id"] for graph in (accepted, working) for item in graph[kind]}
        if any(item not in ids for item in plan[f"remove{kind.title()}"]):
            raise ValueError("Removed identity is absent from both accepted and working graphs.")
    for graph in (accepted, working):
        ids = {item["id"] for item in graph["nodes"]}
        refs = {item["fields"]["parentId"] for item in plan["updateNodes"] if "parentId" in item["fields"]}
        refs |= {item["fields"]["memberOf"] for item in plan["updateNodes"] if "memberOf" in item["fields"]}
        refs |= {item[field] for item in plan["updateEdges"] for field in ("source", "target")}
        if not refs - {None} <= ids:
            raise ValueError("Edit references must exist in accepted and working graphs.")
