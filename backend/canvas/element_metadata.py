"""Persistent application roles and semantic relations, independent of visual ports."""
import unicodedata

ELEMENT_KINDS = (
    "page", "form", "overview", "dialog", "action", "service", "process",
    "entity", "relationship", "storage", "condition", "permission", "constraint",
    "input", "output", "event", "api_contract",
)
EDGE_RELATIONS = ("uses", "communicates_with", "requires", "evidences")
RELATION_REASON_MAX = 1000


def validate_element(node):
    if "element" not in node:
        return
    element = node["element"]
    if (node["kind"] not in ("node", "sector") or not isinstance(element, dict)
            or set(element) != {"kind"} or element["kind"] not in ELEMENT_KINDS):
        raise ValueError("Neplatný druh prvku (element).")


def validate_relation(edge):
    if "relation" in edge and edge["relation"] not in EDGE_RELATIONS:
        raise ValueError("Neplatný význam vazby (relation).")
    if "reason" in edge:
        reason = edge["reason"]
        if ("relation" not in edge or not isinstance(reason, str)
                or not 0 < len(reason) <= RELATION_REASON_MAX or reason != reason.strip()
                or any(unicodedata.category(char) == "Cc" for char in reason)):
            raise ValueError("Neplatné zdůvodnění vazby (reason).")
    if "requirement" in edge:
        requirement = edge["requirement"]
        if (edge.get("relation") != "requires" or not isinstance(requirement, dict)
                or not {"readiness", "revision"} <= set(requirement) <= {"readiness", "revision", "verification"}
                or requirement["readiness"] not in ("design", "implemented", "verified")
                or type(requirement["revision"]) is not int or requirement["revision"] < 0):
            raise ValueError("Neplatný požadovaný vstup (requirement).")
        if "verification" in requirement:
            from backend.brain_opora.determinism.milestone_evidence import descriptor
            verification = requirement["verification"]
            if requirement["readiness"] != "verified" or not isinstance(verification, dict) or set(verification) != {"positive", "negative"}:
                raise ValueError("Verification cases belong to a verified requirement.")
            descriptor({"nodeId": edge["target"], "acceptedRevision": "0" * 40, **verification})


def validate_requirement_cycles(edges, nodes=()):
    """Only blocking requirements must be acyclic; cooperation may be reciprocal.

    Temporary child-to-parent links express inherited requirements without copying
    them to every descendant. Hierarchy alone is acyclic, so each discovered cycle
    contains a requires link. Iterative removal handles all 2000 nodes without recursion.
    """
    outgoing, incoming = {}, {}
    pairs = [(edge["source"], edge["target"]) for edge in edges if edge.get("relation") == "requires"]
    pairs.extend((node["id"], node["parentId"]) for node in nodes if node.get("parentId") is not None)
    for source, target in pairs:
        outgoing.setdefault(source, []).append(target)
        incoming.setdefault(source, 0)
        incoming[target] = incoming.get(target, 0) + 1
    ready = [node for node, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for target in outgoing.get(node, ()):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    if visited != len(incoming):
        raise ValueError("Realizační závislosti (requires) nesmí tvořit cyklus.")
