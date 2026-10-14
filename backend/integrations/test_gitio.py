import subprocess

from backend.integrations import gitio


def test_every_git_call_allows_long_paths(monkeypatch):
    # Worktree v datové složce + hluboké soubory repozitáře přesahují na Windows 260 znaků.
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, b"ok", b"")

    monkeypatch.setattr(gitio.subprocess, "run", fake_run)
    assert gitio.git("repo", "status") == "ok"
    command = seen["command"]
    index = command.index("core.longpaths=true")
    assert command[index - 1] == "-c"
    assert index < command.index("-C")
