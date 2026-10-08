"""One human confirmation for an explicit selection of proposed cards in a sector."""

import copy

from backend.canvas.canvas_service import now
from backend.canvas.graph import valid_id


def confirm_proposals(state_store, payload):
    keys = {"project", "workspace", "sectorId", "nodeIds", "expectedRevision"}
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ValueError("Potvrzení vyžaduje projekt, workspace, sektor, nodeIds a expectedRevision.")
    if not all(valid_id(payload[key]) for key in ("project", "workspace", "sectorId")):
        raise ValueError("Neplatný rozsah potvrzení.")
    ids = payload["nodeIds"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or not all(valid_id(n) for n in ids) or len(set(ids)) != len(ids):
        raise ValueError("Vyberte 1 až 200 různých karet.")
    if type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 0:
        raise ValueError("Potvrzení vyžaduje platnou revizi stavu.")
    project, workspace, sector = (payload[key] for key in ("project", "workspace", "sectorId"))
    canvas = state_store.canvas
    with canvas.graph_lock, canvas.lock:
        graph = canvas.view(project, workspace)["graph"]
        by_id = {node["id"]: node for node in graph["nodes"]}
        if by_id.get(sector, {}).get("kind") != "sector":
            raise ValueError("Hromadné potvrzení vyžaduje sektor.")
        stored = state_store.read(project, workspace)
        if stored["readOnly"] or stored["revision"] != payload["expectedRevision"]:
            raise ValueError("Stav se změnil nebo je pouze ke čtení. Obnovte seznam návrhů.")
        state = copy.deepcopy(stored["state"])
        for node_id in ids:
            node = by_id.get(node_id)
            if node is None or node["kind"] not in ("node", "sector"):
                raise ValueError("Vybraná karta už neexistuje.")
            parent, seen = node["parentId"], set()
            while parent and parent != sector and parent not in seen:
                seen.add(parent)
                parent = by_id.get(parent, {}).get("parentId")
            if parent != sector:
                raise ValueError("Vybraná karta nepatří do sektoru.")
            done = state["nodes"].get(node_id, {}).get("done", {})
            if done.get("by") != "agent" or done.get("confirmed") is not False:
                raise ValueError("Některá karta už nemá návrh agenta. Obnovte seznam.")
            done.update(confirmed=True, by="human", at=now())
        return state_store.save({"project": project, "workspace": workspace,
                                 "expectedRevision": payload["expectedRevision"], "state": state})
