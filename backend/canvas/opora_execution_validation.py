"""Strict bounded execution messages and immutable, accepted contextual assignments."""
import json
import re

from backend.canvas import card_gauge
from backend.canvas.graph import digest, valid_id
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_content_execution import require_accepted_content
from backend.canvas.opora_graph_execution import require_accepted_graph
from backend.canvas.opora_plan_steps import ordered, steps_of
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.sector_status import sector_blockers
from backend.editor.agent_packet.specification_context import capture_specification


def validate(payload, extra):
    if not isinstance(payload, dict) or set(payload) != {"project", "workspace", *extra}:
        raise ValueError("Invalid execution fields.")
    result = scope(payload)
    for key in ("nodeId", "requestId"):
        if key in payload and (not isinstance(payload[key], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", payload[key])):
            raise ValueError("Invalid execution identity.")
    if "ttlSeconds" in payload and (type(payload["ttlSeconds"]) is not int or not 30 <= payload["ttlSeconds"] <= 3600):
        raise ValueError("ttlSeconds must be an integer between 30 and 3600.")
    if "epoch" in payload and (type(payload["epoch"]) is not int or payload["epoch"] < 1):
        raise ValueError("Invalid execution epoch.")
    if "token" in payload and (not isinstance(payload["token"], str) or not re.fullmatch(r"[a-f0-9]{64}", payload["token"])):
        raise ValueError("Invalid execution credential.")
    return result


def result_digest(result):
    if not isinstance(result, dict) or not isinstance(result.get("summary"), str) or not result["summary"].strip():
        raise ValueError("Result requires a nonempty summary.")
    try:
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Result must be bounded JSON.") from exc
    if len(encoded.encode("utf-8")) > 64_000:
        raise ValueError("Result exceeds 64000 bytes.")
    return digest(result)


def assignment(canvas, project, workspace, node, context_version=1, require_graph=True):
    if not isinstance(node, str) or not valid_id(node):
        raise ValueError("Invalid card.")
    context = OporaChangesets(canvas).context(project, workspace)
    if context["readOnly"] or not context["acceptedHead"]:
        raise ValueError("A writable workspace with accepted specifications is required.")
    from backend.library.harness_kit import require_kit_context
    own = next((doc for doc in context["acceptedDocuments"] if doc["nodeId"] == node), {})
    require_kit_context(own.get("fields", {}), context_version)
    view = canvas.view(project, workspace)
    if require_graph:  # Běžící běh hlídá jen výřez své karty; rozdíl grafů blokuje jen nový claim a start.
        require_accepted_graph(canvas, project, workspace, context["acceptedHead"], view["graph"])
    target = next((item for item in view["graph"]["nodes"] if item["id"] == node), None)
    if target is None or target["kind"] not in ("node", "sector"):
        raise ValueError("Card cannot be executed.")
    stored = DesktopV3State(canvas).read(project, workspace)["state"]
    if stored["nodes"].get(node, {}).get("done", {}).get("confirmed") or sector_blockers(view["graph"], stored, node):
        raise ValueError("Card is closed or blocked by its predecessor.")
    captured = capture_specification(canvas, project, workspace, node)
    accepted = {item["nodeId"]: item for item in context["acceptedDocuments"]}
    live = {item["nodeId"]: item for item in context["documents"]}
    relevant = [item["nodeId"] for item in captured["specification"]["cards"]]
    require_accepted_content(canvas, project, workspace, context["acceptedHead"], relevant, view["graph"])
    if any(key not in accepted or digest(accepted[key]) != digest(live.get(key)) for key in relevant):
        raise ValueError("Relevant specifications differ from their accepted revision.")
    # Accepted plan steps of the claimed card are pinned in the immutable snapshot (oporahub-plan-steps.md).
    steps = ordered(steps_of(accepted.get(node, {}).get("fields")))
    return {"acceptedRevision": context["acceptedHead"], "documents": [accepted[key] for key in relevant],
            **captured, "steps": steps, "run": run_profile(target, view["graph"], steps)}


def run_profile(target, graph, steps):
    """Profil běhu dělníka v zadání (docs/navrhy/2026-10-30-metriky-a-spoustece.md §3): jen stabilní struktura karty
    (kroky, soubory, riziko, `fanIn`, `card.effort`), bez stáří a ceny. Běžící běh porovnává `run` ze svého claimu
    (`OporaExecutions.pinned_digest`), takže pozdější změna štítku běh neodvolá."""
    return card_gauge.brief(card_gauge.profile(target, graph, steps))
