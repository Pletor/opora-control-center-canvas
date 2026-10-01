from tools.install_git_hooks import hook_path, install, remove


def repo(tmp_path):
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


def test_install_writes_the_hook(tmp_path):
    root = repo(tmp_path)
    passed, message = install(root)
    assert passed and "nainstalov" in message
    assert "tools/verify.py" in hook_path(root).read_text(encoding="utf-8")


def test_install_keeps_a_foreign_hook_unless_forced(tmp_path):
    root = repo(tmp_path)
    hook_path(root).write_text("#!/bin/sh\necho cizi\n", encoding="utf-8")
    passed, message = install(root)
    assert passed is False and "cizí" in message
    assert "cizi" in hook_path(root).read_text(encoding="utf-8")
    assert install(root, force=True)[0] is True


def test_install_updates_its_own_hook(tmp_path):
    root = repo(tmp_path)
    install(root)
    hook_path(root).write_text("# stary tools/install_git_hooks.py\n", encoding="utf-8")
    passed, message = install(root)
    assert passed and "aktualizov" in message


def test_remove_touches_only_its_own_hook(tmp_path):
    root = repo(tmp_path)
    install(root)
    assert remove(root)[0] is True
    assert not hook_path(root).exists()
    hook_path(root).write_text("#!/bin/sh\necho cizi\n", encoding="utf-8")
    passed, message = remove(root)
    assert passed is False and "cizí" in message


def test_missing_git_folder_is_reported(tmp_path):
    passed, message = install(tmp_path)
    assert passed is False and ".git" in message
