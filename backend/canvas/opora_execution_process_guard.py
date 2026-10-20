"""Serialize legacy process writes against enrollment in any project workspace."""
from copy import deepcopy
from functools import wraps
from inspect import signature

from backend.canvas.project_folder import ProjectFolder
from backend.editor.process.process_store import ProcessStore


def process_mutation_guard(service):
    """File mutation stays inside the enrollment transaction; files are not SQL rollbackable."""
    def decorate(action):
        parameters = signature(action)

        @wraps(action)
        def guarded(*args, **kwargs):
            bound = parameters.bind(*args, **kwargs)
            payload, request = bound.arguments["payload"], bound.arguments["request"]
            project = payload.get("project", "")
            folder = ProjectFolder(service.root, project)
            with service.graph_lock_for(project), service.lock_for(project):
                db = service.db_for(project)
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    process_id = bound.arguments.get("process_id")
                    node = (ProcessStore(folder.path).get(process_id).get("nodeId")
                            if process_id else payload.get("nodeId"))
                    enrolled = db.execute("SELECT 1 FROM opora_execution_epochs"
                                          " WHERE project_id=? AND node_id=? LIMIT 1", (project, node)).fetchone()
                    if enrolled:
                        if getattr(request.state, "actor", None) != "human":
                            raise ValueError("Enrolled cards require execution receipts, not legacy process writes.")
                        normalized = deepcopy(payload)
                        author = {"kind": "human", "name": "Člověk"}
                        normalized["by"] = author
                        if isinstance(normalized.get("evidence"), dict):
                            normalized["evidence"]["by"] = author
                        if isinstance(normalized.get("failure"), dict):
                            normalized["failure"]["reportedBy"] = author
                        bound.arguments["payload"] = normalized
                    return action(*bound.args, **bound.kwargs)

        return guarded
    return decorate
