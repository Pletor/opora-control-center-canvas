# ruff: noqa: TRY004 -- risk validation failures are API domain conflicts.
"""Deterministic server-side risk for validated immutable proposals."""

from backend.canvas.graph import digest

_LEVEL = {"standard": 0, "elevated": 1, "critical": 2}
_CONTENT_FIELDS = {"actions", "rules", "blocks", "materials", "downloadsUrl"}


def _record(proposal):
    if not isinstance(proposal, dict):
        raise ValueError("Proposal risk requires a stored proposal record.")
    return proposal


def _result(level, reasons):
    ordered = sorted(set(reasons))
    return {"level": level, "reasons": ordered, "digest": digest({"level": level, "reasons": ordered})}


def classify_risk(proposal_kind, proposal):
    """Classify a native proposal record; caller validates its full immutable schema first."""
    proposal = _record(proposal)
    reasons = []

    if proposal_kind == "spec":
        # Specification proposal records intentionally have no `kind` field.
        if "kind" in proposal or not isinstance(proposal.get("changes"), list) or not proposal["changes"]:
            raise ValueError("Proposal is not a native specification change.")
        level = "elevated"
        reasons.append("specification_changed")

    elif proposal_kind == "graph-addition":
        if proposal.get("kind") != "graph-additions":
            raise ValueError("Proposal is not a native graph addition.")
        adoption = proposal.get("requiresBaseAdoption")
        parent_manifest = proposal.get("parentGraphManifestId")
        if type(adoption) is not bool or adoption != (parent_manifest is None):
            raise ValueError("Graph addition adoption evidence is inconsistent.")
        level = "elevated"
        reasons.append("graph_addition")
        if adoption:
            level = "critical"
            reasons.append("first_graph_manifest_adoption")

    elif proposal_kind == "graph-change":
        if proposal.get("kind") != "graph-changes":
            raise ValueError("Proposal is not a native graph change.")
        plan = proposal.get("plan")
        if (not isinstance(plan, dict) or not isinstance(plan.get("removeNodes"), list)
                or not isinstance(plan.get("removeEdges"), list)
                or type(plan.get("adoptArchitectureContext")) is not bool):
            raise ValueError("Graph change risk fields are invalid.")
        level = "elevated"
        reasons.append("graph_changed")
        if plan["removeNodes"]:
            level = "critical"
            reasons.append("nodes_removed")
        if plan["removeEdges"]:
            level = "critical"
            reasons.append("edges_removed")
        if plan["adoptArchitectureContext"]:
            level = "critical"
            reasons.append("shared_architecture_context_adopted")

    elif proposal_kind == "content":
        if proposal.get("kind") != "content-proposal":
            raise ValueError("Proposal is not a native content proposal.")
        adoption, changes = proposal.get("requiresBaseContentAdoption"), proposal.get("changes")
        if type(adoption) is not bool or not isinstance(changes, list) or not changes:
            raise ValueError("Content proposal risk fields are invalid.")
        level = "standard"
        if adoption:
            level = "critical"
            reasons.append("first_content_manifest_adoption")
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("Content proposal contains an invalid change.")
            kind, field = change.get("kind"), change.get("field")
            if kind == "text" and field == "text":
                reasons.append("text_changed")
            elif kind == "drawing" and field == "scene":
                reasons.append("drawing_changed")
            elif kind == "config" and field in _CONTENT_FIELDS:
                if field == "materials":
                    reasons.append("materials_changed")
                else:
                    reasons.append(f"control_field_changed:{field}")
                    level = "elevated" if _LEVEL[level] < _LEVEL["elevated"] else level
            else:
                raise ValueError("Content proposal contains an unsupported native change.")

    else:
        raise ValueError("Unsupported proposal kind for risk classification.")

    return _result(level, reasons)
