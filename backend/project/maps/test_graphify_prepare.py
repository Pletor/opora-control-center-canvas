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
