from .desktop_v3_packets import ancestor_ids, drawing_chain, memory_for
from .desktop_v3_state import DesktopV3State, default_state
from .wireframe_context import wireframe_context


def build_planning_context(canvas, project, workspace, layer):
    """Sestaví jen uložené aplikační podklady, nikoli obsah připojené složky.

    Kresby předků a paměť projektu přicházejí ze stejného sdíleného sestavení jako
    balíček pro agenta (desktop_v3_packets), aby neexistovala druhá odlišná pravda.
    """
    with canvas.graph_lock:
        config = canvas.project_hub.settings(project)
        view = canvas.view(project, workspace)
        graph = view["graph"]
        by_id = {node["id"]: node for node in graph["nodes"]}
        if layer and layer not in by_id:
            raise ValueError("Vrstva plánování v projektu neexistuje.")
        core = {node["id"] for node in graph["nodes"] if node["parentId"] == (layer or None)}
        current = layer or None
        while current is not None:
            core.add(current)
            current = by_id[current]["parentId"]
        selected = set(core)
        links = []
        for edge in graph["edges"]:
            if edge["source"] in core or edge["target"] in core:
                links.append(edge)
                selected.update((edge["source"], edge["target"]))
        specs = []
        if not view["readOnly"]:
            with canvas.lock:
                for node_id in sorted(core):
                    specs.append({"nodeId": node_id, **canvas.specs.read((project, workspace, node_id))})
        drawing = canvas.drawing(project, workspace, layer)
        wireframe = wireframe_context(project, workspace, layer, drawing)
        wireframe["available"] = drawing["available"]
        drawings = drawing_chain(canvas, project, workspace, layer, by_id)
        state_store = getattr(canvas, "desktop_v3_state", None) or DesktopV3State(canvas)
        with canvas.lock:
            stored = (
                state_store.current(project, workspace)
                if not view["readOnly"]
                else {"revision": 0, "state": default_state()}
            )
        lineage = [layer, *ancestor_ids(by_id, layer)] if layer else []
        layer_path = (by_id[layer].get("sourceRef") or {}).get("path", "") if layer else ""
        memory = memory_for(stored, lineage, [layer_path], "")
        source = config["project"]
        return {
            "project": {key: source.get(key) for key in ("id", "name", "sourceKind")},
            "workspace": workspace,
            "layer": layer,
            "configRevision": config["revision"],
            "settings": config["settings"],
            "graph": {
                "digest": view["digest"], "sha": view["sha"], "source": view["source"],
                "totalNodes": len(graph["nodes"]), "includedNodes": len(selected),
                "nodes": [{key: node[key] for key in ("id", "parentId", "kind", "name", "purpose")} for node in graph["nodes"] if node["id"] in selected],
                "edges": links,
            },
            "nodeSpecs": specs,
            "nodeTexts": [] if view["readOnly"] else [{"nodeId": node_id, **canvas.texts.access(project, workspace, node_id)} for node_id in sorted(core)],
            "wireframe": wireframe,
            "drawings": drawings,
            "memory": memory,
            "policy": {"purpose": "proposal_only", "tools": 0, "sourceFilesRead": False, "automaticWrites": False},
            "notes": ["Pouze uložené podklady. Neuložené změny editoru nejsou zahrnuté.", "Souřadnice wireframu jsou autoritativní; bloky jsou kontejnery a akce popis požadovaného chování, nikoli příkazy k vykonání.", "Kresby předků (drawings) a paměť projektu (memory) pocházejí ze stejného sestavení jako balíček pro agenta.", "Výstup modelu je návrh k posouzení, nikoli dokončená implementace."],
        }
