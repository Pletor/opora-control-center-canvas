"""Live navigation metadata only; never an execution assignment or capability."""
from urllib.parse import urlencode


def links(project, workspace, node, execution=None):
    query = urlencode({"project": project, "workspace": workspace, "nodeId": node})
    scope = urlencode({"project": project, "workspace": workspace})
    return {"context": f"/api/oporahub/executions/context?{query}",
            "claim": "/api/oporahub/executions/claim",
            "results": f"/api/oporahub/executions/{execution}/results?{scope}" if execution else None,
            "proposalContext": f"/api/oporahub/changesets/context?{scope}",
            "brief": f"/api/desktop-v3/node-brief?{query}"}


def brief_metadata(project, workspace, node):
    query = urlencode({"project": project, "workspace": workspace, "nodeId": node})
    return {"schema": "opora.process-navigation/1", "live": True,
            "process": f"/api/oporahub/process?{query}",
            "links": links(project, workspace, node),
            "authority": "Live navigation only; claim an immutable execution assignment before work."}
