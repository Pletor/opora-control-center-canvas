"""Actual accepted draft promotion switches all normal writers to journaled SQL."""
import copy

import pytest

from backend.canvas.opora_context_graph_storage import promote_sql_draft
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.canvas.test_opora_graph_proposals import graphs as graph_fixture
from backend.canvas.test_opora_graph_proposals import service as canvas_fixture
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_context_events import checkpoint, transitions
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority

graphs, service = graph_fixture, canvas_fixture


def promote(service, head):
    with service.graph_lock_for('draft'), service.lock_for('draft'):
        db = service.db_for('draft')
        with db:
            db.execute('BEGIN IMMEDIATE')
            return promote_sql_draft(service, 'draft', 'draft', head)


def test_promotion_preserves_graph_head_and_historical_draft_then_all_writes_are_journaled(graphs, service):
    head = accept(graphs, proposal(graphs))['id']
    before = copy.deepcopy(service.view('draft', 'draft'))
    db = service.db_for('draft')
    legacy = db.execute("SELECT graph FROM drafts WHERE id='draft'").fetchone()[0]
    assert WorkspaceGraphAuthority(db, 'draft', 'draft').read() is None
    promote(service, head)
    promoted = service.view('draft', 'draft')
    assert promoted['graph'] == before['graph'] and promoted['digest'] == before['digest']
    assert ChangesetRepository(db, 'draft', 'draft').head() == head
    origin = checkpoint(db, 'draft')['sequence']
    graph = copy.deepcopy(before['graph'])
    next(node for node in graph['nodes'] if node['id'] == 'a')['name'] = 'Edited'
    service.save_graph('draft', 'draft', graph, before['digest'])
    assert service.view('draft', 'draft')['graph'] == graph
    assert any(event['sourceTable'] == 'workspace_graph_authority' for event in transitions(db, 'draft', origin))
    assert db.execute("SELECT graph FROM drafts WHERE id='draft'").fetchone()[0] == legacy
    # Restore a semantic match before accepting a new ordinary proposal.
    changed = service.view('draft', 'draft')
    service.save_graph('draft', 'draft', before['graph'], changed['digest'])
    item = proposal(graphs, 'After promotion')
    previous = WorkspaceGraphAuthority(db, 'draft', 'draft').read()['revision']
    accept(graphs, item)
    assert WorkspaceGraphAuthority(db, 'draft', 'draft').read()['revision'] == previous + 1
    assert any(node['id'] == item['refs']['new'] for node in service.view('draft', 'draft')['graph']['nodes'])
    assert db.execute("SELECT graph FROM drafts WHERE id='draft'").fetchone()[0] == legacy


@pytest.mark.parametrize('mutation', ["UPDATE workspace_graph_authority SET digest='corrupt'", 'DELETE FROM workspace_graph_authority'])
def test_corrupt_or_deleted_promoted_authority_never_uses_legacy(graphs, service, mutation):
    promote(service, accept(graphs, proposal(graphs))['id'])
    with service.db_for('draft') as db:
        db.execute(mutation)
    with pytest.raises(ValueError, match='fallback is forbidden'):
        service.view('draft', 'draft')


def test_never_promoted_accepted_v1_draft_uses_existing_storage(graphs, service):
    accept(graphs, proposal(graphs))
    db = service.db_for('draft')
    before = service.view('draft', 'draft')
    graph = copy.deepcopy(before['graph'])
    graph['nodes'][0]['name'] = 'Still v1'
    service.save_graph('draft', 'draft', graph, before['digest'])
    assert service.view('draft', 'draft')['graph'] == graph
    assert WorkspaceGraphAuthority(db, 'draft', 'draft').read() is None
    assert db.execute('SELECT count(*) FROM opora_context_coverage').fetchone()[0] == 0


def test_deleted_authority_enrolled_before_journal_never_falls_back(graphs, service):
    from backend.canvas.architecture_graph import split
    from database.repositories.opora_context_events import enroll
    accept(graphs, proposal(graphs))
    graph = service.view('draft', 'draft')['graph']
    db = service.db_for('draft')
    with db:
        db.execute('BEGIN IMMEDIATE')
        WorkspaceGraphAuthority(db, 'draft', 'draft').enroll(split(graph)[1])
    with db:
        db.execute('BEGIN IMMEDIATE')
        enroll(db, 'draft')
        db.execute('DELETE FROM workspace_graph_authority')
    with pytest.raises(ValueError, match='fallback is forbidden'):
        service.view('draft', 'draft')


def test_requires_transaction_manifest_current_head_and_accepted_semantics(graphs, service):
    original = graphs.context(project='draft', workspace='draft')['acceptedHead']
    with pytest.raises(RuntimeError):
        promote_sql_draft(service, 'draft', 'draft', original)
    with pytest.raises(ValueError, match='manifest'):
        promote(service, original)
    head = accept(graphs, proposal(graphs))['id']
    with pytest.raises(ValueError, match='manifest'):
        promote(service, original)
    before = service.view('draft', 'draft')
    graph = copy.deepcopy(before['graph'])
    graph['nodes'][0]['name'] = 'Unapproved'
    service.save_graph('draft', 'draft', graph, before['digest'])
    with pytest.raises(ValueError, match='differs from the accepted graph'):
        promote(service, head)
    assert WorkspaceGraphAuthority(service.db_for('draft'), 'draft', 'draft').read() is None


def test_promotion_rollback_preserves_v1_and_idempotency(graphs, service):
    head = accept(graphs, proposal(graphs))['id']
    db = service.db_for('draft')
    with service.graph_lock_for('draft'), service.lock_for('draft'):
        db.execute('BEGIN IMMEDIATE')
        promote_sql_draft(service, 'draft', 'draft', head)
        db.rollback()
    assert WorkspaceGraphAuthority(db, 'draft', 'draft').read() is None
    assert checkpoint_absent(db)
    first = promote(service, head)
    assert promote(service, head) == first


def checkpoint_absent(db):
    return db.execute('SELECT count(*) FROM opora_context_coverage').fetchone()[0] == 0


def test_frozen_journal_does_not_break_ordinary_graph_editing(graphs, service):
    promote(service, accept(graphs, proposal(graphs))['id'])
    with service.db_for('draft') as db:
        db.execute("UPDATE opora_context_coverage SET frozen='limit reached'")
    before = service.view('draft', 'draft')
    graph = copy.deepcopy(before['graph'])
    graph['nodes'][0]['name'] = 'Ordinary edit still works'
    service.save_graph('draft', 'draft', graph, before['digest'])
    assert service.view('draft', 'draft')['graph'] == graph
    with pytest.raises(ValueError, match='frozen'):
        checkpoint(db, 'draft')


def test_architecture_strip_updates_authority_not_historical_draft(graphs, service):
    from backend.canvas.migrate_architecture import _strip_workspaces
    promote(service, accept(graphs, proposal(graphs))['id'])
    db = service.db_for('draft')
    legacy = db.execute("SELECT graph FROM drafts WHERE id='draft'").fetchone()[0]
    origin = checkpoint(db, 'draft')['sequence']
    with service.graph_lock_for('draft'):
        _strip_workspaces(service, 'draft', {'moved': [{'id': 'a', 'type': 'node'}],
                                          'strip': [{'workspace': 'draft', 'action': 'stripped'}]})
    assert all(node['id'] != 'a' for node in service.view('draft', 'draft')['graph']['nodes'])
    assert db.execute("SELECT graph FROM drafts WHERE id='draft'").fetchone()[0] == legacy
    assert any(event['sourceTable'] == 'workspace_graph_authority' for event in transitions(db, 'draft', origin))


@pytest.mark.parametrize('kind', ['local', 'empty'])
def test_actual_non_builtin_project_promotes_and_survives_reopen(service, tmp_path, kind):
    from backend.canvas.canvas_service import CanvasService
    from backend.canvas.opora_changesets import OporaChangesets
    from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.canvas.test_opora_changesets import AGENT, HUMAN
    if kind == 'empty':
        project = service.project_hub.empty_project({'name': 'Empty', 'confirmed': True})['id']
    else:
        source = tmp_path / 'source'
        source.mkdir()
        project = service.project_hub.local_project({'name': 'Local', 'path': str(source), 'confirmed': True})['id']
    scope = {'project': project, 'workspace': 'draft'}
    initial = service.view(project, 'draft')
    service.save_graph(project, 'draft', copy.deepcopy(service.view('draft', 'draft')['graph']), initial['digest'])
    specs = OporaChangesets(service)
    current = specs.context(project, 'draft')
    specs.baseline({**scope, 'subject': 'Baseline', 'expectedAcceptedHead': None,
                    'expectedGraphDigest': current['graphDigest'],
                    'expectedSpecificationsVersion': current['specificationsVersion']}, HUMAN)
    graphs = OporaGraphProposals(service)
    current = graphs.context(**scope)
    item = graphs.create({**scope, 'parentRevision': current['acceptedHead'],
                          'expectedGraphDigest': current['graphDigest'], 'subject': 'Card',
                          'plan': {'nodes': [{'ref': 'card', 'kind': 'node', 'name': 'Card'}]}}, AGENT)
    head = OporaGraphAcceptance(service).accept(item['id'], {**scope, 'expectedAcceptedHead': current['acceptedHead'],
        'expectedGraphDigest': current['graphDigest'], 'adoptBaseGraphDigest': item['graphDigest']}, HUMAN)['id']
    before = service.view(project, 'draft')['graph']
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        with db:
            db.execute('BEGIN IMMEDIATE')
            promote_sql_draft(service, project, 'draft', head)
    assert service.view(project, 'draft')['graph'] == before
    reopened = CanvasService(service.root)
    try:
        assert reopened.view(project, 'draft')['graph'] == before
        assert WorkspaceGraphAuthority(reopened.db_for(project), project, 'draft').read()
    finally:
        reopened.close()
