"""Reviewed native fields and semantic edge ports retain graph invariants and authority."""
import pytest
from backend.canvas.test_opora_graph_changes import edits, approve, change
from backend.canvas.test_opora_graph_proposals import graphs, service


def test_native_optional_fields_and_non_next_edges_review_accept_remove(edits, service):
    before = service.view('draft', 'draft')['graph']
    item = change(edits, {'draftVersion': 3,
        'updateNodes': [{'id': 'a', 'fields': {'card': {'layer': 'backend', 'status': 'ready'},
                                             'blockOffsets': {'action': {'dx': 12, 'dy': 18}}}}],
        'edges': [{'from': '@a', 'to': '@b', 'port': 'action'}]})
    assert service.view('draft', 'draft')['graph'] == before
    edge = item['additions']['edges'][0]['id']
    assert item['changes']['nodes'][0]['fields'] == ['blockOffsets', 'card']
    approve(edits, item)
    edited = change(edits, {'draftVersion': 3, 'updateEdges': [{'id': edge, 'source': 'b', 'target': 'a', 'port': 'rule'}]})
    assert edited['changes']['edges'][0]['proposedWorking']['port'] == 'rule'
    approve(edits, edited)
    removed = change(edits, {'draftVersion': 3, 'removeEdges': [edge],
                            'updateNodes': [{'id': 'a', 'fields': {'card': None, 'blockOffsets': None}}]})
    approve(edits, removed)
    graph = service.view('draft', 'draft')['graph']
    assert not any(row['id'] == edge for row in graph['edges'])
    node = next(row for row in graph['nodes'] if row['id'] == 'a')
    assert 'card' not in node and 'blockOffsets' not in node


def test_native_field_validation_shared_architecture_and_next_cycle_remain_guarded(edits):
    for plan in (
        {'updateNodes': [{'id': 'a', 'fields': {'card': {'status': 'done'}}}]},
        {'updateNodes': [{'id': 'a', 'fields': {'id': 'renamed'}}]},
        {'edges': [{'from': '@a', 'to': '@b', 'port': 'flow'}]},
        {'edges': [{'from': '@a', 'to': '@b', 'port': 'invalid'}]},
    ):
        before = edits.list('draft', 'draft')
        with pytest.raises(ValueError):
            change(edits, {'draftVersion': 3, **plan})
        assert edits.list('draft', 'draft') == before


def test_native_next_cycle_rejected_before_proposal_persistence(edits, service):
    plan = {'draftVersion': 3, 'edges': [{'from': '@a', 'to': '@b', 'port': 'next'},
                                       {'from': '@b', 'to': '@a', 'port': 'next'}]}
    before = edits.list('draft', 'draft')
    with pytest.raises(ValueError, match='cyklus'):
        change(edits, plan)
    assert edits.list('draft', 'draft') == before


def test_legacy_pending_cycle_rejected_at_acceptance_without_writes(edits, service, monkeypatch):
    from backend.canvas import opora_graph_change_state as safety
    original = safety.check_save
    monkeypatch.setattr(safety, 'check_save', lambda *_: None)
    item = change(edits, {'draftVersion': 3, 'edges': [{'from': '@a', 'to': '@b', 'port': 'next'},
                                                     {'from': '@b', 'to': '@a', 'port': 'next'}]})
    monkeypatch.setattr(safety, 'check_save', original)
    before = edits.context('draft', 'draft')
    state = service.desktop_v3_state.current('draft', 'draft') if hasattr(service, 'desktop_v3_state') else None
    with pytest.raises(ValueError, match='cyklus'):
        approve(edits, item)
    assert edits.context('draft', 'draft') == before
    assert not edits.read('draft', 'draft', item['id'])['accepted']
    if state is not None:
        assert service.desktop_v3_state.current('draft', 'draft') == state


def test_non_next_process_loop_remains_valid(edits, service):
    item = change(edits, {'draftVersion': 3, 'edges': [{'from': '@a', 'to': '@b', 'port': 'action'},
                                                     {'from': '@b', 'to': '@a', 'port': 'rule'}]})
    approve(edits, item)
    assert len(service.view('draft', 'draft')['graph']['edges']) == 2
