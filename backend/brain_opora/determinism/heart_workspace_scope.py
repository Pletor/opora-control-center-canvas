"""Existing project Heart bootstrap delegation, bounded to native planning/context routes."""
import re

READS = {
    '/api/view', '/api/oporahub/graph-proposals/context', '/api/oporahub/graph-proposals',
    '/api/oporahub/changesets/context', '/api/node-spec', '/api/node-text',
    '/api/desktop-v3/state', '/api/oporahub/agent-state', '/api/brain/heart/context',
}
WRITES = {'/api/canvas-plan', '/api/oporahub/graph-proposals', '/api/oporahub/baselines'}


def permits(service, project, workspace, path, method):
    if not any(row['id'] == workspace for row in service.workspaces(project)):
        return False
    if method in ('GET', 'HEAD'):
        return path in READS or bool(re.fullmatch(r'/api/oporahub/graph-proposals/[^/]+', path))
    return method == 'POST' and (path in WRITES or bool(re.fullmatch(r'/api/oporahub/graph-proposals/[^/]+/accept', path)))
