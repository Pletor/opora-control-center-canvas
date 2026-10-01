from backend.integrations.gitio import git
from backend.project.maps.map_git_exclude import ensure_excluded


def repository(path):
    path.mkdir()
    git(path, 'init', '--initial-branch=main')
    return path


def test_unignored_folder_goes_to_local_exclude_not_gitignore(tmp_path):
    root = repository(tmp_path / 'repo')
    (root / '.gitignore').write_text('node_modules/\n')
    assert ensure_excluded(root, 'archify-out') is True
    assert '/archify-out/' in (root / '.git/info/exclude').read_text().splitlines()
    assert (root / '.gitignore').read_text() == 'node_modules/\n'
    (root / 'archify-out').mkdir()
    (root / 'archify-out/SPEC.md').write_text('x')
    assert git(root, 'status', '--porcelain', '--untracked-files=all') == '?? .gitignore'
    assert ensure_excluded(root, 'archify-out') is False
    assert (root / '.git/info/exclude').read_text().count('/archify-out/') == 1


def test_folder_already_ignored_by_project_is_left_alone(tmp_path):
    root = repository(tmp_path / 'repo')
    (root / '.gitignore').write_text('graphify-out/\n')
    before = (root / '.git/info/exclude').read_text() if (root / '.git/info/exclude').exists() else ''
    assert ensure_excluded(root, 'graphify-out') is False
    after = (root / '.git/info/exclude').read_text() if (root / '.git/info/exclude').exists() else ''
    assert after == before


def test_project_without_git_is_untouched(tmp_path):
    assert ensure_excluded(tmp_path, 'graphify-out') is False
    assert not (tmp_path / '.git').exists()
