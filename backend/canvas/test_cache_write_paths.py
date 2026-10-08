"""Stejné produkční zápisy s předem zahřátou cache; oracle je čtení bez cache.

Scénáře zachovávají vlastní doménové aserce. Navíc před každým cílovým zápisem
zahřejeme všechny cache a po něm porovnáme nové čtení s nezávislým cache-miss.
"""
from importlib import import_module
import inspect

import pytest
from fastapi.testclient import TestClient


CASES = [
    ('state', 'editor.agent_memory.test_agent_output', 'test_output_writes_block_status_edge_report_done_proposal_and_decision', '/api/desktop-v3/state'),
    ('graph', 'canvas.test_canvas_plan', 'test_full_plan_lands_and_node_brief_reads_it', '/api/graph'),
    ('node-spec', 'editor.node.test_node_specs', 'test_spec_persists_across_application_restart_without_changing_graph', '/api/node-spec'),
    ('node-text', 'editor.node.test_node_text', 'test_text_is_scoped_revisioned_and_part_of_saved_context', '/api/node-text'),
    ('canvas-plan', 'canvas.test_canvas_plan', 'test_full_plan_lands_and_node_brief_reads_it', '/api/canvas-plan'),
    ('pipeline', 'editor.agent_memory.test_card_pipeline', 'test_router_routes_from_server_profile_and_frontier_dispatches_the_session', '/api/desktop-v3/pipeline'),
    ('lease', 'editor.agent_memory.test_card_leases', 'test_lease_survives_restart_and_frontier_unclaims_on_expiry', '/api/desktop-v3/lease'),
    ('agent-output', 'editor.agent_memory.test_agent_output', 'test_output_writes_block_status_edge_report_done_proposal_and_decision', '/api/desktop-v3/agent-output'),
    ('agent-workspace', 'editor.agent_memory.test_agent_workspace', 'test_save_writes_revision_and_partial_update_keeps_other_sections', '/api/desktop-v3/agent-workspace'),
    ('block', 'editor.agent_memory.test_block_access', 'test_add_appends_root_block_and_renumbers', '/api/desktop-v3/block'),
    ('rule', 'editor.agent_memory.test_memory_items', 'test_agent_rule_is_only_a_proposal_until_a_human_approves_it', '/api/desktop-v3/rule'),
    ('decision', 'editor.agent_memory.test_decision_versions', 'test_correction_preserves_original_rejects_forks_and_warns_successor', '/api/desktop-v3/decision'),
    ('realize-source', 'canvas.test_source_realization', 'test_realization_requires_merge_and_disk_then_tracks_disappearance', '/api/desktop-v3/realize-source'),
    ('versions-save', 'editor.canvas_versions.test_canvas_versions', 'test_non_empty_canvas_without_version_is_dirty_and_save_cleans_it', '/api/canvas-versions'),
    ('versions-restore', 'editor.canvas_versions.test_canvas_versions', 'test_restore_returns_graph_and_state_and_saves_dirty_canvas_first', '/api/canvas-versions/restore'),
    ('settings', 'project_setup.test_project_hub', 'test_profile_round_trip_and_cas', '/api/project-settings'),
    ('import-project', 'project_setup.test_project_hub', 'test_local_project_is_metadata_only_and_persists_with_its_draft', '/api/local-project'),
    ('remove-project', 'project_setup.test_project_hub', 'test_empty_settings_cas_and_archived_project_are_guarded', '/api/remove'),
]


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in ('observedAt', 'serverNow')}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def snapshot(client, body):
    scope = {key: body.get(key, 'draft') for key in ('project', 'workspace')}
    queries = [(url, scope) for url in ('/api/view', '/api/desktop-v3/state', '/api/canvas-versions', '/api/desktop-v3/leases')]
    queries += [('/api/project-settings', {'project': scope['project']}), ('/api/bootstrap', {})]
    if body.get('node'):
        queries += [(url, {**scope, 'node': body['node']}) for url in ('/api/node-spec', '/api/node-text')]
    if body.get('nodeId'):
        queries += [('/api/desktop-v3/agent-workspace', {**scope, 'nodeId': body['nodeId']})]
    result = {}
    for url, params in queries:
        response = client.get(url, params=params)
        result[url] = (response.status_code, stable(response.json()))
    return result


@pytest.mark.parametrize('case,module,name,target', CASES, ids=[case[0] for case in CASES])
def test_write_reads_fresh_value_with_warm_cache(case, module, name, target, tmp_path, monkeypatch):
    original_post = TestClient.post
    verified = []

    def post(client, url, *args, **kwargs):
        body = kwargs.get('json', {})
        if url != target:
            return original_post(client, url, *args, **kwargs)
        before = snapshot(client, body)
        response = original_post(client, url, *args, **kwargs)
        if response.status_code == 200:
            after = snapshot(client, body)
            # Všechny instance cache, včetně privátní cache CanvasVersions.
            with monkeypatch.context() as uncached:
                uncached.setenv('OPORA_READ_CACHE', '0')
                cold = snapshot(client, body)
            assert after == cold, case
            # Duplicitní import / save může být záměrný no-op, alespoň jeden zápis
            # scénáře ale musí opravdu změnit čtený obsah, ne pouze vrátit HTTP 200.
            verified.append(after != before)
        return response

    monkeypatch.setattr(TestClient, 'post', post)
    scenario = getattr(import_module('backend.' + module), name)
    arguments = {'tmp_path': tmp_path}
    if 'monkeypatch' in inspect.signature(scenario).parameters:
        arguments['monkeypatch'] = monkeypatch
    scenario(**arguments)
    assert any(verified), f'{case}: nebyl ověřen žádný skutečně měnící zápis na {target}'
