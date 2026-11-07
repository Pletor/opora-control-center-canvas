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
                     "baseSha": "0" * 40, "next": "report"}, "state": "open"},
            ("POST", f"/work/{TICKET}/run"): {}} | (routes or {})

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
    assert [call[1] for call in server.calls] == [f"/work/{TICKET}", f"/work/{TICKET}/run"] * 2


def test_task_prints_parent_and_target(repo, monkeypatch, capsys):
    server = Server(repo)
    server.routes[("GET", f"/work/{TICKET}")]["work"] |= {"baseSha": "abcdef0123", "target": "develop"}
    out = run(monkeypatch, capsys, server, repo, "task", "--ticket", TICKET)[1]
    assert "Rodič: develop@abcdef0; začlení se do: develop" in out and "Relace:" not in out


def test_task_survives_missing_run_route_but_not_other_errors(repo, monkeypatch, capsys):
    def refused(status):
        return HTTPError("u", status, "x", {}, io.BytesIO(json.dumps({"detail": "Neznámá cesta API"}).encode()))

    code, out = run(monkeypatch, capsys, Server(repo, {("POST", f"/work/{TICKET}/run"): refused(404)}), repo, "task",
                    "--ticket", TICKET)
    assert code == 0 and "Relace: server ji neeviduje (starší verze)" in out and "Úkol" in out
    code, out = run(monkeypatch, capsys, Server(repo, {("POST", f"/work/{TICKET}/run"): refused(409)}), repo, "task",
                    "--ticket", TICKET)
    assert code == 1 and "Server odmítl (409" in out


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


def marked(repo, trailer=True):
    return {("GET", f"/work/{TICKET}"): {"work": {"repository": str(repo), "branch": "feat/x", "mark": "OP-3F9A1C"}},
            ("POST", f"/work/{TICKET}/report"): {"ok": True}}


def test_task_sends_run_with_session_from_hook_and_prints_mark(repo, monkeypatch, capsys):
    (repo / ".opora").mkdir()
    (repo / ".opora" / "session.json").write_text(json.dumps({"sessionId": "s-1", "transcriptPath": "t.jsonl"}))
    server = Server(repo, marked(repo))
    code, out = run(monkeypatch, capsys, server, repo, "task", "--ticket", TICKET)
    method, path, body, _ = server.calls[-1]
    assert code == 0 and (method, path) == ("POST", f"/work/{TICKET}/run")
    assert body == {"sessionId": "s-1", "agent": "terminal", "transcriptPath": "t.jsonl"}
    assert "Vodotisk: OP-3F9A1C" in out and 'trailer "Opora-Mark: OP-3F9A1C"' in out
    assert "Vodotisk: neevidován" in run(monkeypatch, capsys, Server(repo), repo, "task", "--ticket", TICKET)[1]


def test_report_without_trailer_exits_2_without_post_and_with_trailer_passes(repo, monkeypatch, capsys):
    server = Server(repo, marked(repo))
    code, out = run(monkeypatch, capsys, server, repo, "report", "--ticket", TICKET)
    assert code == 2 and "Opora-Mark: OP-3F9A1C" in out and "git commit --amend" in out
    assert not [c for c in server.calls if c[0] == "POST"]
    assert run(monkeypatch, capsys, server, repo, "report", "--ticket", TICKET, "--allow-unmarked")[0] == 0
    git(repo, "commit", "-q", "--allow-empty", "-m", "x\n\nOpora-Mark: OP-3F9A1C")
    server.calls.clear()
    assert run(monkeypatch, capsys, server, repo, "report", "--ticket", TICKET)[0] == 0
    assert [c[0] for c in server.calls] == ["GET", "POST"]


def test_trace_prints_layers_and_sentence(repo, monkeypatch, capsys):
    answer = {"ticket": {"title": "Datový uzel", "body": {"essence": "E"}}, "card": {"name": "Karta"}, "revision": "r2",
              "plan": [{"order": 1, "title": "Krok"}],
              "runs": [{"agent": "terminal", "startedAt": "2026-11-06", "fromSha": "a" * 40, "status": "verified"}],
              "commits": [{"sha7": "abc1234", "title": "feat", "status": "inferred", "runId": None}],
              "code": [{"path": "a.py", "line": 3, "symbol": "def f", "status": "verified"}],
              "pr": {"number": 12, "state": "OPEN"}, "gaps": [{"text": "Commit bez relace"}], "sentence": "OP-3F9A1C: E."}
    server = Server(repo, {("GET", "/trace/OP-3F9A1C"): answer})
    code, out = run(monkeypatch, capsys, server, repo, "trace", "--mark", "OP-3F9A1C")
    assert code == 0 and "OP-3F9A1C: Datový uzel" in out and "terminal 2026-11-06 od aaaaaaa verified" in out
    assert "abc1234 feat inferred bez relace" in out and "a.py:3 def f verified" in out
    assert "PR: number=12, state=OPEN" in out and "Commit bez relace" in out and out.rstrip().endswith("OP-3F9A1C: E.")
    server = Server(repo, marked(repo) | {("GET", "/trace/OP-3F9A1C"): {}})
    assert run(monkeypatch, capsys, server, repo, "trace", "--ticket", TICKET)[0] == 0


def test_board_prints_text_of_route_and_mine_flag(repo, monkeypatch, capsys):
    shown = "Pletor: Na plátně 0 kuliček.\nČeká na člověka:\n"

    class TextServer(Server):
        def __call__(self, request, timeout):
            self.calls.append((request.get_method(), request.full_url, request.get_header("Accept")))
            return io.BytesIO(shown.encode())

    server = TextServer(repo)
    code, out = run(monkeypatch, capsys, server, repo, "board", "--project", "p", "--workspace", "main", "--mine")
    assert code == 0 and out == shown
    assert server.calls[0][1].endswith("/board.txt?project=p&workspace=main&mine=1") and server.calls[0][2] == "text/plain"
    code, out = run(monkeypatch, capsys, server, repo, "board")
    assert code == 2 and "projekt" in out
