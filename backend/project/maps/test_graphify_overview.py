from backend.project.maps.graphify_overview import community_name, overview


def node(id, community, path, kind='code'):
    return {'id': id, 'label': id, 'community': community, 'source_file': path,
            'file_type': kind, 'community_name': 'Community %s' % community}


def test_names_come_from_common_folder_prefix():
    assert community_name(['frontend/editor/canvas/a.ts', 'frontend/editor/canvas/b/c.ts']) == 'frontend/editor/canvas'
    assert community_name(['backend/x.py', 'backend/x.py']) == 'backend/x.py'
    assert community_name(['backend/a.py', 'frontend/b.ts', 'backend/c/d.py']) == 'backend a další'
    assert community_name(['README.md', 'package.json']) == 'smíšené'
    assert community_name([]) == 'smíšené'


def test_overview_aggregates_communities_and_cross_edges():
    graph = {'nodes': [
        node('a', 1, 'frontend/editor/canvas/a.ts'), node('b', 1, 'frontend\\editor\\canvas\\b.ts'),
        node('c', 1, 'frontend/editor/canvas/b.ts', 'doc'), node('d', 2, 'backend/api/x.py'),
        node('e', 2, 'backend/api/y.py'), {'id': 'loose', 'label': 'loose'},
    ], 'links': [
        {'source': 'a', 'target': 'b', 'weight': 1}, {'source': 'a', 'target': 'c', 'weight': 1},
        {'source': 'a', 'target': 'd', 'weight': 2}, {'source': 'e', 'target': 'b', 'weight': 0.5},
        {'source': 'loose', 'target': 'a'},
    ]}
    result = overview(graph)
    assert result['counts'] == {'nodes': 6, 'edges': 5, 'communities': 2}
    first, second = result['communities']
    assert first['id'] == 1 and first['name'] == 'frontend/editor/canvas' and first['rawName'] == 'Community 1'
    assert first['size'] == 3 and first['files'] == 2 and first['kinds'] == {'code': 2, 'doc': 1}
    assert first['top'][0] == {'id': 'a', 'label': 'a', 'source_file': 'frontend/editor/canvas/a.ts', 'degree': 4}
    assert first['paths'] == ['frontend/editor']
    assert second['name'] == 'backend/api'
    assert result['edges'] == [{'source': 1, 'target': 2, 'weight': 2.5, 'count': 2}]
    assert result['truncated'] is False


def test_overview_truncates_communities_and_edges(monkeypatch):
    import backend.project.maps.graphify_overview as module
    monkeypatch.setattr(module, 'MAX_COMMUNITIES', 3)
    monkeypatch.setattr(module, 'MAX_EDGES', 2)
    nodes = [node('n%d_%d' % (c, i), c, 'pkg%d/f.py' % c) for c in range(5) for i in range(c + 1)]
    links = [{'source': 'n%d_0' % a, 'target': 'n%d_0' % b, 'weight': a + b} for a in range(5) for b in range(a + 1, 5)]
    result = overview({'nodes': nodes, 'links': links})
    assert [item['id'] for item in result['communities']] == [4, 3, 2]
    assert [(e['source'], e['target']) for e in result['edges']] == [(3, 4), (2, 4)]
    assert result['truncated'] is True
    assert result['counts']['communities'] == 5


def test_repeated_names_get_deeper_folder_then_node_then_order():
    graph = {'nodes': [
        node('run.py', 1, 'backend/live_run/run.py'), node('y', 1, 'backend/live_run/y.py'), node('k', 1, 'backend/k.py'),
        node('z.py', 2, 'backend/api/z.py'), node('w', 2, 'backend/api/w.py'), node('v', 2, 'backend/v.py'),
        node('q.py', 3, 'backend/api/q.py'), node('p', 3, 'backend/api/p.py'),
        dict(node('s1', 4, 'shared/s.json'), label='enum'), dict(node('s2', 5, 'shared/s.json'), label='enum'), node('solo', 6, 'docs/solo.md'),
    ], 'links': [{'source': 'z.py', 'target': 'w'}, {'source': 'q.py', 'target': 'p'}]}
    names = sorted(item['name'] for item in overview(graph)['communities'])
    assert names == ['backend/api · p', 'backend/api · w', 'backend/live_run', 'docs/solo.md',
                     'shared/s.json · enum', 'shared/s.json · enum (2)']
