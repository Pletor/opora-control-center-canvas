"""Request-local native read snapshots; source authorization is never memoized."""
from contextlib import ExitStack, contextmanager

from backend.editor.research import model, question_journal


@contextmanager
def materialization(canvas, candidates, authorize):
    from backend.editor.research.knowledge import _bindings

    scopes = {(item["project"], item["workspace"]) for item in candidates}
    sources = set(scopes)
    for project, workspace in sorted(scopes):
        authorize(project, workspace, False)
        nodes = {item["node"]["id"] for item in candidates
                 if (item["project"], item["workspace"]) == (project, workspace)}
        for binding in _bindings(canvas, project, workspace):
            if binding["archived"] or binding["scopeNodeId"] not in nodes:
                continue
            source = binding["source"]
            try:
                authorize(source["projectId"], source["workspaceId"], False)
            except (ValueError, OSError, model.GateError):
                continue
            sources.add((source["projectId"], source["workspaceId"]))
    # Listing/detail can repair question projections. Finish these writes before
    # opening consistent read snapshots, so freshly projected records stay visible.
    projects = set()
    for project, workspace in sorted(sources):
        try:
            authorize(project, workspace, False)
            question_journal.reconcile(canvas, project, workspace)
            projects.add(project)
        except (ValueError, OSError, model.GateError):
            if (project, workspace) in scopes:
                raise
    with ExitStack() as stack:
        for project in sorted(projects):
            stack.enter_context(canvas.reading(project))
            if canvas.lock_for(project)._is_owned():
                stack.enter_context(canvas.steady_reads(project))
        yield
