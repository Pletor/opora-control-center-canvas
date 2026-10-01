import pytest

from backend.integrations.gitio import git
from backend.project.maps.map_git_exclude import ensure_excluded


def repository(path):
    path.mkdir()
    git(path, 'init', '--initial-branch=main')
    return path


def exclude_lines(root):
    path = root / '.git/info/exclude'
    return path.read_text().splitlines() if path.exists() else []


def untracked(root):
    return set((git(root, 'status', '--porcelain', '--untracked-files=all') or '').splitlines())


def test_unignored_folder_goes_to_local_exclude_not_gitignore(tmp_path):
    root = repository(tmp_path / 'repo')
    (root / '.gitignore').write_text('node_modules/\n')
    assert ensure_excluded(root, 'archify-out') is True
    assert '/archify-out/' in exclude_lines(root)
    assert (root / '.gitignore').read_text() == 'node_modules/\n'
    (root / 'archify-out').mkdir()
    (root / 'archify-out/SPEC.md').write_text('x')
    assert untracked(root) == {'?? .gitignore'}
    assert ensure_excluded(root, 'archify-out') is False
    assert exclude_lines(root).count('/archify-out/') == 1


def test_blank_line_in_gitignore_does_not_fake_ignored_folder(tmp_path):
    # Git 2.47 hlásí `složka/` jako ignorovanou, když za pravidlem složky následuje prázdný řádek.
    root = repository(tmp_path / 'repo')
    (root / '.gitignore').write_text('node_modules/\n\ndocs/\n')
    (root / 'archify-out').mkdir()
    (root / 'archify-out/SPEC.md').write_text('x')
    assert ensure_excluded(root, 'archify-out') is True
    assert '/archify-out/' in exclude_lines(root)
    assert untracked(root) == {'?? .gitignore'}


def test_folder_already_ignored_by_project_is_left_alone(tmp_path):
    root = repository(tmp_path / 'repo')
    (root / '.gitignore').write_text('docs/\n\ngraphify-out/\n')
    before = exclude_lines(root)
    assert ensure_excluded(root, 'graphify-out') is False
    (root / 'graphify-out').mkdir()
    assert ensure_excluded(root, 'graphify-out') is False
    assert exclude_lines(root) == before


def test_versioned_folder_hides_only_opora_bookkeeping(tmp_path):
    root = repository(tmp_path / 'repo')
    (root / 'graphify-out/memory/cards').mkdir(parents=True)
    (root / 'graphify-out/graph.json').write_text('{}')
    git(root, 'add', 'graphify-out')
    git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-m', 'mapa')
    assert ensure_excluded(root, 'graphify-out') is True
    lines = exclude_lines(root)
    assert '/graphify-out/' not in lines
    assert {'/graphify-out/opora-build.lock', '/graphify-out/opora-receipt.json', '/graphify-out/*.tmp'} <= set(lines)
    (root / 'graphify-out/memory/cards/new.md').write_text('karta')
    (root / 'graphify-out/opora-receipt.json').write_text('{}')
    (root / 'graphify-out/opora-build.lock').write_text('')
    (root / 'graphify-out/graph.json.tmp').write_text('{}')
    assert untracked(root) == {'?? graphify-out/memory/cards/new.md'}
    assert ensure_excluded(root, 'graphify-out') is False
    assert exclude_lines(root) == lines


def test_invalid_folder_is_rejected(tmp_path):
    root = repository(tmp_path / 'repo')
    with pytest.raises(ValueError):
        ensure_excluded(root, '../out')


def test_project_without_git_is_untouched(tmp_path):
    assert ensure_excluded(tmp_path, 'graphify-out') is False
    assert not (tmp_path / '.git').exists()
