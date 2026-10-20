"""Verify declared outputs on disk and retain reported merge provenance."""

import copy
import re
from datetime import UTC, datetime

from backend.canvas.design_metadata import validate_design


def validate_realization(value):
    if not isinstance(value, dict) or set(value) != {"commit", "prUrl", "verifiedAt"}:
        raise ValueError("Realizace vyžaduje commit, prUrl a verifiedAt.")
    if not isinstance(value["commit"], str) or (value["commit"] and not re.fullmatch(r"[0-9a-fA-F]{7,64}", value["commit"])):
        raise ValueError("Commit musí být SHA (7 až 64 hex znaků), nebo prázdný.")
    if not isinstance(value["prUrl"], str) or not (value["commit"] or value["prUrl"]):
        raise ValueError("Vyplňte commit nebo odkaz na PR.")
    if value["prUrl"]:
        validate_design({"artifactUrl": value["prUrl"], "version": "merge"})
    try:
        if not isinstance(value["verifiedAt"], str) or datetime.fromisoformat(value["verifiedAt"]).tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("verifiedAt musí být čas se zónou.") from None


def source_status(canvas, project, workspace):
    with canvas.reading(project):
        graph = canvas.view(project, workspace)["graph"]
        try:
            root = canvas.workspace_sources.root(project, workspace)
        except (ValueError, OSError):
            root = None
        result = {}
        for node in graph["nodes"]:
            ref = node.get("sourceRef")
            if not ref:
                continue
            status = "unavailable"
            if root is not None:
                try:
                    target = canvas.workspace_sources.target(root, ref["path"])
                    status = "present" if (target.is_dir() if ref["kind"] == "directory" else target.is_file()) else "missing"
                except FileNotFoundError:
                    status = "missing"
                except (ValueError, OSError):
                    status = "unavailable"
            result[node["id"]] = {"status": status, "path": ref["path"], "origin": ref["origin"]}
        return {"nodes": result, "checkedAt": datetime.now(UTC).isoformat()}


def realize_source(state, payload, *, actor="system"):
    if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "nodeId", "digest", "commit", "prUrl"}:
        raise ValueError("Realizace vyžaduje project, workspace, nodeId, digest, commit a prUrl.")
    canvas = state.canvas
    project, workspace = payload["project"], payload["workspace"]
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        if actor != "human":
            from backend.canvas.opora_execution_guard import legacy_lease
            legacy_lease(canvas.db_for(project), project, workspace, payload["nodeId"])
        view = canvas.view(project, workspace)
        if view["readOnly"] or view["digest"] != payload["digest"]:
            raise ValueError("Plátno je pouze ke čtení nebo se změnilo. Obnovte ho.")
        graph = copy.deepcopy(view["graph"])
        node = next((n for n in graph["nodes"] if n["id"] == payload["nodeId"]), None)
        if not node or not node.get("sourceRef"):
            raise ValueError("Karta nemá cestu výstupu.")
        evidence = state.current(project, workspace)["state"]["nodes"].get(node["id"], {}).get("evidence", {})
        if evidence.get("merge", {}).get("status") != "passed":
            raise ValueError("Převod zdroje vyžaduje uložený důkaz merge se stavem passed.")
        current = source_status(canvas, project, workspace)["nodes"][node["id"]]
        if current["status"] != "present":
            raise ValueError("Cestu nelze ověřit jako existující soubor nebo složku.")
        realization = {"commit": payload["commit"], "prUrl": payload["prUrl"], "verifiedAt": datetime.now(UTC).isoformat()}
        validate_realization(realization)
        node["sourceRef"]["origin"] = "existing"
        node["realization"] = realization
        return canvas.save_graph(project, workspace, graph, payload["digest"])
