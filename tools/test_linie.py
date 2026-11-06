import io
import json
import subprocess
from urllib.error import HTTPError, URLError

import pytest

from tools import linie

TICKET = "tk_abc"


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid", "-C", str(root), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "develop")
    (root / "a.txt").write_text("a")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "base")
    git(root, "switch", "-q", "-c", "feat/x")
    return root


class Server:
    """Podvržené API: odpovědi podle (metoda, cesta), zapisuje každé volání."""

    def __init__(self, repo, routes=None):
        self.calls = []
        self.routes = {("GET", f"/work/{TICKET}"): {
            "ticket": {"id": TICKET, "title": "Datový uzel", "body": {"essence": "E", "build": "B", "doneCriteria": "D"}},
            "work": {"repository": str(repo), "worktree": None, "branch": "feat/x", "baseBranch": "develop",
                     "baseSha": "0" * 40, "next": "report"}, "state": "open"}} | (routes or {})

    def __call__(self, request, timeout):
        path = request.full_url.split("/api/pletor/linie", 1)[1].split("?")[0]
        body = json.loads(request.data) if request.data else None
        self.calls.append((request.get_method(), path, body, dict(request.header_items())))
        answer = self.routes[(request.get_method(), path)]
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(json.dumps(answer).encode())


def run(monkeypatch, capsys, server, cwd, *argv):
    monkeypatch.setattr(linie, "_open", server)
    code = linie.main(list(argv), cwd=cwd)
    return code, capsys.readouterr().out


def test_task_in_wrong_branch_or_directory_stops_with_exit_2_and_keeps_files(repo, tmp_path, monkeypatch, capsys):
    (repo / "a.txt").write_text("rozpracováno")
    git(repo, "switch", "-q", "-c", "feat/jina")
    server = Server(repo)
    code, out = run(monkeypatch, capsys, server, repo, "task", "--ticket", TICKET)
    assert code == 2 and "Jiný kontext: očekává se feat/x" in out and "jsi na feat/jina" in out
    assert "Nezačínej, nic nezahazuj." in out
    assert (repo / "a.txt").read_text() == "rozpracováno" and git(repo, "branch", "--show-current") == "feat/jina"
    elsewhere = tmp_path / "jinde"
    elsewhere.mkdir()
    code, out = run(monkeypatch, capsys, server, elsewhere, "task", "--ticket", TICKET)
    assert code == 2 and "Jiný kontext" in out
    assert not (repo / ".opora").exists() and not (elsewhere / ".opora").exists()


def test_task_remembers_ticket_and_session_restart_finds_it(repo, monkeypatch, capsys):
    (repo / "a.txt").write_text("změna")
    server = Server(repo)
    code, out = run(monkeypatch, capsys, server, repo, "task", "--ticket", TICKET, "--project", "P", "--workspace", "W")
    assert code == 0 and "Podstata: E" in out and "a.txt" in out and "další krok: report" in out
    assert json.loads((repo / ".opora" / "linie.json").read_text()) == {"ticketId": TICKET, "project": "P",
                                                                       "workspace": "W"}
    assert ".opora" not in git(repo, "status", "--porcelain")
    code, out = run(monkeypatch, capsys, server, repo, "task")
    assert code == 0 and f"Úkol {TICKET}" in out
    assert [call[1] for call in server.calls] == [f"/work/{TICKET}"] * 2


def test_task_without_memory_picks_ball_by_current_branch(repo, monkeypatch, capsys):
    board = {"balls": [{"ticketId": TICKET, "branch": "feat/x"}, {"ticketId": "tk_jiny", "branch": "feat/y"}]}
    server = Server(repo, {("GET", "/board"): board})
    monkeypatch.setenv("OPORA_PROJECT", "P")
    monkeypatch.setenv("OPORA_WORKSPACE", "W")
    assert run(monkeypatch, capsys, server, repo, "task")[0] == 0
    board["balls"].append({"ticketId": "tk_dalsi", "branch": "feat/x"})
    (repo / ".opora" / "linie.json").unlink()
    code, out = run(monkeypatch, capsys, server, repo, "task")
    assert code == 2 and "víc úkolů" in out and "tk_dalsi" in out


def test_report_sends_head_checks_and_identity(repo, monkeypatch, capsys):
    monkeypatch.setenv("OPORA_AGENT_NAME", "terminal")
    server = Server(repo, {("POST", f"/work/{TICKET}/report"): {"ok": True}})
    code, _ = run(monkeypatch, capsys, server, repo, "report", "--ticket", TICKET, "--check", "npm test=green")
    _, _, body, headers = server.calls[-1]
    assert code == 0 and body == {"sha": git(repo, "rev-parse", "HEAD"), "checks": [{"name": "npm test",
                                                                                     "status": "green"}],
                                  "worktree": str(repo)}
    assert headers["X-opora-actor"] == "agent; name=terminal"


def test_merge_conflict_prints_message_exits_1_and_never_merges(repo, monkeypatch, capsys):
    refused = HTTPError("u", 409, "Conflict", {}, io.BytesIO(json.dumps(
        {"code": "head_moved", "message": "Přijetí platí pro starší SHA."}).encode()))
    server = Server(repo, {("POST", f"/work/{TICKET}/merge"): refused})
    head = git(repo, "rev-parse", "develop")
    code, out = run(monkeypatch, capsys, server, repo, "merge", "--ticket", TICKET)
    assert code == 1 and "head_moved" in out and "Přijetí platí pro starší SHA." in out
    assert git(repo, "rev-parse", "develop") == head


def test_server_down_exits_3_and_keeps_code(repo, monkeypatch, capsys):
    (repo / "a.txt").write_text("rozpracováno")
    server = Server(repo, {("GET", f"/work/{TICKET}"): URLError("refused")})
    code, out = run(monkeypatch, capsys, server, repo, "task", "--ticket", TICKET)
    assert code == 3 and out.startswith("Evidence nedostupná, kód zachován, blokace:")
    assert (repo / "a.txt").read_text() == "rozpracováno"
