from backend.integrations.gitio import git
from backend.project.maps.graphify_runtime import prepare_output
from backend.project.maps.graphify_worker import MAX_CODE_BYTES, MAX_CODE_FILES, corpus_error


def test_failed_run_leaves_main_clean(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init', '--initial-branch=main')
    folder = prepare_output(root.resolve())
    # Co běh stihne vytvořit, než selže (zámek, cache), nesmí zašpinit main pro synchronizaci.
    (folder / 'opora-build.lock').write_bytes(b'')
    (folder / 'cache').mkdir()
    (folder / 'cache/x.json').write_text('{}')
    assert git(root, 'status', '--porcelain', '--untracked-files=all') in (None, '')


def test_corpus_limits():
    assert corpus_error(0, 0)
    assert corpus_error(MAX_CODE_FILES, MAX_CODE_BYTES) is None
    assert '1–1200' in corpus_error(MAX_CODE_FILES + 1, 1)
    assert corpus_error(1, MAX_CODE_BYTES + 1) == 'Zdrojový kód překračuje 32 MiB.'


def test_html_is_requested_only_when_cluster_only_skipped_it(tmp_path, monkeypatch):
    import backend.project.maps.graphify_worker as worker
    calls = []
    monkeypatch.setattr(worker, 'original_cli', calls.append)
    produced = tmp_path / 'graphify-out'
    produced.mkdir()
    worker.ensure_html(tmp_path)
    assert calls == [['export', 'html', '--graph', str(produced / 'graph.json'), '--node-limit', '5000']]
    (produced / 'graph.html').write_text('<html>full</html>')
    worker.ensure_html(tmp_path)
    assert len(calls) == 1


def test_large_graph_gets_aggregated_html_from_original_cli(tmp_path, real_graphify):
    # Nad 5000 uzlů `cluster-only` graph.html vynechá (agent-office: 5482 uzlů) a publikace pak selhala.
    import json
    import subprocess
    from pathlib import Path

    from backend.project.maps.graphify_runtime import clean_environment
    produced = tmp_path / 'graphify-out'
    produced.mkdir()
    nodes = [{'id': f'n{i}', 'label': f'n{i}', 'community': i % 2} for i in range(5001)]
    links = [{'source': 'n0', 'target': 'n1', 'relation': 'calls', 'confidence': 'EXTRACTED'}]
    (produced / 'graph.json').write_text(json.dumps({'directed': False, 'multigraph': False, 'graph': {},
                                                     'nodes': nodes, 'links': links}), encoding='utf-8')
    worker = Path(__file__).with_name('graphify_worker.py').resolve().parent
    script = f'import sys;from pathlib import Path;sys.path.insert(0, {str(worker)!r});import graphify_worker as w;w.ensure_html(Path({str(tmp_path)!r}))'
    result = subprocess.run([real_graphify, '-I', '-X', 'utf8', '-c', script], cwd=tmp_path, env=clean_environment(),
                            capture_output=True, text=True, encoding='utf-8', timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'graph.html written (aggregated: 2 community nodes' in result.stdout
    assert (produced / 'graph.html').stat().st_size > 0
