"""Observed scoped code location at claim, separate from accepted plan authority."""
import re
import subprocess

from backend.canvas.graph import digest
from backend.integrations.gitio import git
from backend.project.workspace.workspace_sources import SourceMissing, WorkspaceSources


def capture(service, project, workspace):
    try:
        root = WorkspaceSources(service).root(project, workspace)
    except SourceMissing:
        return {'available': False, 'reason': 'source_unavailable'}
    if root is None:
        return {'available': False, 'reason': 'no_source'}
    try:
        head = git(root, 'rev-parse', '--verify', '--quiet', 'HEAD^{commit}', timeout=5, optional=True)
        branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', timeout=5, optional=True)
        after = git(root, 'rev-parse', '--verify', '--quiet', 'HEAD^{commit}', timeout=5, optional=True)
    except (OSError, subprocess.SubprocessError):
        return {'available': False, 'reason': 'git_unavailable', 'worktree': str(root)}
    if not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', head):
        return {'available': False, 'reason': 'no_git_commit', 'worktree': str(root)}
    if head != after:
        raise ValueError('Working code HEAD changed during claim capture; retry the claim.')
    return {'available': True, 'worktree': str(root), 'headSha': head, 'branch': branch,
            'coverage': 'commit-and-location; uncommitted contents are not captured'}


def attach(service, repo, node, captured, pin):
    if pin is None:  # Historical v1 assignment comparison remains unchanged.
        return captured
    value = {**captured, 'codeContext': capture(service, *repo.scope)}
    for old in repo.history(node):
        assignment = old.get('assignment', {})
        if (old['acceptedRevision'] == captured['acceptedRevision']
                and assignment.get('contextVersion') == captured.get('contextVersion')):
            value['resumedFrom'] = {'executionId': old['executionId'],
                'acceptedRevision': old['acceptedRevision'],
                'codeContext': assignment.get('codeContext', {'available': False, 'reason': 'legacy_untracked'})}
            break
    pin['assignmentDigest'] = digest(value)
    return value
