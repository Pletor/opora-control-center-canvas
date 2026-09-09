from .wireframe_context import wireframe_context


def build_planning_context(canvas, project, workspace, layer):
    """Sestaví jen uložené aplikační podklady, nikoli obsah připojené složky."""
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
            "policy": {"purpose": "proposal_only", "tools": 0, "sourceFilesRead": False, "automaticWrites": False},
            "notes": ["Pouze uložené podklady. Neuložené změny editoru nejsou zahrnuté.", "Souřadnice wireframu jsou autoritativní; bloky jsou kontejnery a akce popis požadovaného chování, nikoli příkazy k vykonání.", "Výstup modelu je návrh k posouzení, nikoli dokončená implementace."],
        }
