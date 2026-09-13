"""Pracovní strom skrývá šum, nemění soubory a stránkuje až po filtraci."""
from fastapi.testclient import TestClient
from backend.integrations.tests.test_workspace_sources import ORIGIN, attach

from backend.app.factory import create_app


def test_working_tree_hides_ignored_noise_before_pagination_and_prioritizes_src(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    for name in ['aaa', 'src', 'backend', 'node_modules', '.venv', 'dist', 'generated']:
        (source / name).mkdir()
        (source / name / 'keep.txt').write_text('untouched', encoding='utf-8')
    (source / '.gitignore').write_text('generated/\n*.log\n!important.log\n', encoding='utf-8')
    (source / 'debug.log').write_text('debug', encoding='utf-8')
    (source / 'important.log').write_text('important', encoding='utf-8')
    before = sorted(str(p.relative_to(source)) for p in source.rglob('*'))
    with TestClient(create_app(tmp_path/'data'), base_url=ORIGIN) as client:
        pid = attach(client, source)
        params = {'project':pid,'workspace':'draft','visibility':'working','limit':2}
        first = client.get('/api/workspace/tree',params=params).json()
        assert [e['name'] for e in first['entries']] == ['src', 'backend']
        entries = first['entries'][:]
        page = first
        while page['hasMore']:
            page = client.get('/api/workspace/tree',params={**params,'offset':page['nextOffset']}).json()
            entries += page['entries']
        assert [e['name'] for e in entries] == ['src','backend','aaa','.gitignore','important.log']
        assert first['total'] == len(entries) == 5
        assert first['hiddenCount'] == 5
        all_page = client.get('/api/workspace/tree',params={**params,'visibility':'all','limit':200}).json()
        assert all_page['total'] == 10
        assert 'node_modules' in [e['name'] for e in all_page['entries']]
    assert sorted(str(p.relative_to(source)) for p in source.rglob('*')) == before
    assert (source/'node_modules/keep.txt').read_text() == 'untouched'


def test_nested_ignore_negation_and_ignored_parent_do_not_leak(tmp_path):
    source = tmp_path/'source'
    (source/'src/private').mkdir(parents=True)
    (source/'.gitignore').write_text('*.tmp\n/src/private/\n',encoding='utf-8')
    (source/'src/.gitignore').write_text('!keep.tmp\n/private/*.txt\n',encoding='utf-8')
    for name in ['drop.tmp','keep.tmp','App.tsx']:
        (source/'src'/name).write_text(name,encoding='utf-8')
    (source/'src/private/.gitignore').write_text('!*.txt\n',encoding='utf-8')
    (source/'src/private/secret.txt').write_text('not for context',encoding='utf-8')
    with TestClient(create_app(tmp_path/'data'),base_url=ORIGIN) as client:
        pid = attach(client,source)
        params = {'project':pid,'workspace':'draft','visibility':'working','path':'src'}
        page = client.get('/api/workspace/tree',params=params).json()
        assert {e['name'] for e in page['entries']} == {'.gitignore','keep.tmp','App.tsx'}
        hidden = client.get('/api/workspace/tree',params={**params,'path':'src/private'}).json()
        assert hidden['entries'] == [] and hidden['total'] == 0
        assert client.get('/api/workspace/tree',params={**params,'visibility':'invalid'}).status_code == 422
        assert client.get('/api/workspace/tree',params={**params,'path':'../outside'}).status_code == 409


def test_oversized_ignore_is_explicit_failure_not_false_filtered_success(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    (source/'.gitignore').write_bytes(b'x'*262145)
    with TestClient(create_app(tmp_path/'data'),base_url=ORIGIN) as client:
        pid = attach(client,source)
        params = {'project':pid,'workspace':'draft','visibility':'working'}
        response = client.get('/api/workspace/tree',params=params)
        assert response.status_code == 409 and '256 KiB' in response.json()['error']
        assert client.get('/api/workspace/tree',params={**params,'visibility':'all'}).status_code == 200
