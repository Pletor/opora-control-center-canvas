"""Stropy dávek srdce: parametry uzlu `agent.claude` v aktivní verzi sdíleného toku Srdce v1 (docs/navrhy/2026-11-13-pruhled-srdce.md §4).

Stejně jako `model_settings`: zápis je nová verze toku a driver ji čte každý tick, takže platí hned. Tok je jeden pro
celou aplikaci, takže strop platí pro všechny projekty (jedno rozhraní pro všechny projekty).
"""
import copy

from backend.flow import workflows
from backend.flow.catalogs.heart import seed
from backend.flow.catalogs.heart.nodes import AGENT_DEFAULTS

NODE = "agent.claude"
BOUNDS = {"per_hour": (1, 60), "per_project": (1, 4), "rate_sleep_seconds": (60, 3 * 3600)}


def _active(db):
    workflow_id, version_id = seed.ensure_active(db)
    return workflow_id, workflows.get_version(db, version_id)


def _node(graph):
    return next(node for node in graph["nodes"] if node["type"] == NODE)


def read(db):
    params = {**AGENT_DEFAULTS, **(_node(_active(db)[1]["graph"]).get("params") or {})}
    return {key: int(params[key]) for key in BOUNDS} | {"bounds": {key: list(value) for key, value in BOUNDS.items()}}


def write(db, values):
    """`values` = podmnožina `BOUNDS`; celé číslo v mezích, jinak ValueError."""
    if not values or not set(values) <= set(BOUNDS):
        raise ValueError(f"Strop je jeden z {', '.join(BOUNDS)}.")
    for key, value in values.items():
        low, high = BOUNDS[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} je celé číslo {low}–{high}.")
    workflow_id, active = _active(db)
    graph = copy.deepcopy(active["graph"])
    _node(graph).setdefault("params", {}).update(values)
    draft = workflows.create_draft(db, workflow_id, graph, parent_version_id=active["id"])
    workflows.set_candidate(db, draft["id"])
    workflows.activate(db, draft["id"])
    return read(db)
