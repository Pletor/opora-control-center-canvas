"""Model a poradce srdce: parametry uzlu `model.claude` v aktivní verzi sdíleného toku Srdce v1 (M2e).
Zápis je nová verze toku (kopie aktivního grafu), driver ji čte každý tick, takže platí od další dávky."""
import copy

from backend.agi_pletor.llm_settings.claude import EFFORTS, MODELS
from backend.flow import workflows
from backend.flow.catalogs.heart import seed

NODE = "model.claude"


def _active(db):
    workflow_id, version_id = seed.ensure_active(db)
    return workflow_id, workflows.get_version(db, version_id)


def _node(graph):
    return next(node for node in graph["nodes"] if node["type"] == NODE)


def read(db):
    params = _node(_active(db)[1]["graph"])["params"]
    return {"model": params.get("model") or "haiku", "advisor": params.get("advisor") or "opus", "models": MODELS,
            "effort": params.get("effort") or None, "efforts": EFFORTS}


def write(db, model, advisor, effort=None):
    """`effort` None nebo "" = výchozí; poradce effort nemá (Claude Code pro něj nemá přepínač)."""
    for alias in (model, advisor):
        if alias not in {m["id"] for m in MODELS}:
            raise ValueError(f"Neznámý model „{alias}“; platné jsou {', '.join(m['id'] for m in MODELS)}.")
    if effort and effort not in EFFORTS:
        raise ValueError(f"Neznámý effort „{effort}“; platné jsou {', '.join(EFFORTS)}.")
    workflow_id, active = _active(db)
    graph = copy.deepcopy(active["graph"])
    _node(graph)["params"].update(model=model, advisor=advisor, effort=effort or None)
    draft = workflows.create_draft(db, workflow_id, graph, parent_version_id=active["id"])
    workflows.set_candidate(db, draft["id"])
    workflows.activate(db, draft["id"])
    return read(db)
