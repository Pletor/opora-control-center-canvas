"""Fronta úkolů: zápis, `next` (idempotentní, nejstarší, návrat úkolů prošlých relací), `report` a události `gate.task`."""
import json
import subprocess
from datetime import UTC, datetime, timedelta

import pytest

from backend.brain_opora.determinism import gate, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.task_payloads import task_body
from backend.canvas.canvas_service import CanvasService
from database.repositories.gate_sessions import GateSessionStore

WORKER = {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}
SHA = "ABCDEF1234567"
GREEN = [{"name": "pytest", "status": "green"}]
RED = [{"name": "pytest", "status": "red", "output": "1 failed"}]


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def worker(service, now=None):
    """Relace pracovníka; s `now` v minulosti vznikne relace s už prošlým tokenem."""
    issued = gate.tokens.issue_worker(service, "draft", "draft", {"name": "dev"}, now)
    return GateSessionStore(service.db_for("draft")).get(issued["sessionId"])


def create(service, title, node=None):
    payload = {"project": "draft", "workspace": "draft", "title": title, "body": {"do": title}}
    return task_queue.create(service, payload | ({"nodeId": node} if node else {}))


def report(service, session, task_id, checks):
    return task_queue.report(service, session, {"taskId": task_id, "sha": SHA, "summary": "s", "checks": checks})


def task_events(service):
    rows = service.db_for("draft").execute("SELECT data FROM opora_events WHERE kind='gate.task' ORDER BY id").fetchall()
    return [json.loads(row[0])["status"] for row in rows]


def test_task_body_fills_the_fixed_shape_and_refuses_bad_fields():
    assert task_body({"do": "x"}) == {"why": "", "do": "x", "files": [], "doneWhen": [], "dontTouch": [],
                                      "context": {}, "commit": "", "model": "sonnet"}
    for body in ({}, {"do": " "}, {"do": "x", "extra": 1}, {"do": "x", "model": "gpt"}, {"do": "x", "files": "a"},
                 {"do": "x", "dontTouch": [{"path": "a"}]}, {"do": "x", "context": {"who": "?"}}):
        with pytest.raises(GateError):
            task_body(body)
    with pytest.raises(GateError) as clash:
        task_body({"do": "x", "files": ["src/Layout.tsx"], "dontTouch": [{"path": "src/Layout.tsx", "heldBy": "menu"}]})
    assert clash.value.code == "files_held" and "src/Layout.tsx" in str(clash.value)


def test_next_is_idempotent_takes_the_oldest_and_reports_close_tasks(service):
    first, second = create(service, "První", "n1"), create(service, "Druhý")
    session = worker(service)
    got = task_queue.next_task(service, session, {})
    assert got["task"]["id"] == first["taskId"] and got["task"]["body"]["do"] == "První"
    assert task_queue.next_task(service, session, None)["task"]["id"] == first["taskId"]
    assert report(service, session, first["taskId"], GREEN) == {"task": {"id": first["taskId"], "status": "done",
                                                                          "attempts": 0}}
    assert task_queue.next_task(service, session, {})["task"]["id"] == second["taskId"]
    assert report(service, session, second["taskId"], RED)["task"] == {"id": second["taskId"], "status": "ready",
                                                                       "attempts": 1}
    assert task_queue.next_task(service, session, {})["task"]["id"] == second["taskId"]
    assert report(service, session, second["taskId"], GREEN + RED)["task"]["status"] == "failed"
    empty = task_queue.next_task(service, session, {})
    assert empty["task"] is None and isinstance(empty["plan"], list)
    runs = service.db_for("draft").execute("SELECT scope_id, sha, status FROM check_runs ORDER BY recorded_at").fetchall()
    assert [tuple(row) for row in runs] == [("n1", SHA.lower(), "green"), (second["taskId"], SHA.lower(), "red"),
                                            (second["taskId"], SHA.lower(), "green"), (second["taskId"], SHA.lower(), "red")]
    assert task_events(service) == ["ready", "ready", "assigned", "done", "assigned", "assigned", "failed"]


def test_report_refuses_foreign_task_bad_sha_and_no_checks(service):
    task = create(service, "Úkol")
    mine, other = worker(service), worker(service)
    task_queue.next_task(service, mine, {})
    for session, body, code in (
            (other, {"taskId": task["taskId"], "sha": SHA, "summary": "", "checks": GREEN}, "task_not_assigned"),
            (mine, {"taskId": task["taskId"], "sha": "xyz", "summary": "", "checks": GREEN}, "invalid_sha"),
            (mine, {"taskId": task["taskId"], "sha": SHA, "summary": "", "checks": []}, "checks_required"),
            (mine, {"taskId": "ht_none", "sha": SHA, "summary": "", "checks": GREEN}, "task_not_found")):
        with pytest.raises(GateError) as caught:
            task_queue.report(service, session, body)
        assert caught.value.code == code and caught.value.hint
    with pytest.raises(GateError):
        task_queue.next_task(service, mine, {"x": 1})


def test_task_of_an_expired_session_returns_to_ready_on_next(service):
    task = create(service, "Úkol")
    old = worker(service, datetime.now(UTC) - timedelta(hours=9))
    assert task_queue.next_task(service, old, {})["task"]["id"] == task["taskId"]
    fresh = worker(service)
    assert task_queue.next_task(service, fresh, {})["task"]["id"] == task["taskId"]
    assert task_queue.list_tasks(service, "draft", "draft", "assigned")["tasks"][0]["sessionId"] == fresh["id"]


def test_cancel_and_list(service):
    task = create(service, "Úkol")
    assert task_queue.cancel(service, "draft", task["taskId"])["status"] == "cancelled"
    with pytest.raises(GateError) as caught:
        task_queue.cancel(service, "draft", task["taskId"])
    assert caught.value.code == "task_closed"
    assert task_queue.list_tasks(service, "draft", "draft", "ready") == {"tasks": []}
    assert [t["status"] for t in task_queue.list_tasks(service, "draft", "draft")["tasks"]] == ["cancelled"]
    for call in (lambda: task_queue.list_tasks(service, "draft", "draft", "lost"),
                 lambda: task_queue.cancel(service, "nikde", task["taskId"]),
                 lambda: task_queue.create(service, {"project": "draft", "workspace": "draft", "title": "", "body": {}})):
        with pytest.raises(GateError):
            call()
    assert task_events(service) == ["ready", "cancelled"]


def test_heart_writes_ordered_tasks_and_order_is_checked(service):
    payload = {"project": "draft", "workspace": "draft", "title": "Krok", "body": {"do": "x"}}
    later = task_queue.create(service, payload | {"order": 2}, created_by="heart")
    sooner = task_queue.create(service, payload | {"order": 1}, created_by="heart")
    assert (later["createdBy"], later["order"]) == ("heart", 2)
    assert task_queue.next_task(service, worker(service), {})["task"]["id"] == sooner["taskId"]
    assert task_queue.cancel(service, "draft", later["taskId"], by="heart")["status"] == "cancelled"
    actors = service.db_for("draft").execute(
        "SELECT DISTINCT actor_name FROM opora_events WHERE kind='gate.task' AND actor_kind='agent'").fetchall()
    assert {row[0] for row in actors} >= {"heart"}
    for order in (-1, "1", 1.5, True, 10**7):
        with pytest.raises(GateError):
            task_queue.create(service, payload | {"order": order})
    with pytest.raises(ValueError):
        task_queue.create(service, payload, created_by="worker")


def test_release_gives_the_held_task_back_with_a_reason(service):
    task = create(service, "Úkol")
    mine, other = worker(service), worker(service)
    task_queue.next_task(service, mine, {})
    report(service, mine, task["taskId"], RED)
    task_queue.next_task(service, mine, {})
    body = {"taskId": task["taskId"], "reason": "Potřebuji soubor z dontTouch."}
    for session, payload, code in ((other, body, "task_not_assigned"), (mine, {**body, "taskId": "ht_none"},
                                   "task_not_found"), (mine, {"taskId": task["taskId"]}, "invalid_payload"),
                                   (mine, {**body, "reason": "x" * 401}, "invalid_payload")):
        with pytest.raises(GateError) as caught:
            task_queue.release(service, session, payload)
        assert caught.value.code == code and caught.value.hint
    assert task_queue.release(service, mine, body) == {"task": {"id": task["taskId"], "status": "ready", "attempts": 1}}
    held = task_queue.list_tasks(service, "draft", "draft")["tasks"][0]
    assert (held["status"], held["sessionId"]) == ("ready", None)
    rows = service.db_for("draft").execute("SELECT data FROM opora_events WHERE kind='gate.task' ORDER BY id").fetchall()
    assert json.loads(rows[-1][0]) == {"taskId": task["taskId"], "status": "ready", "reason": body["reason"]}
    with pytest.raises(GateError) as again:
        task_queue.release(service, mine, body)
    assert again.value.code == "task_not_assigned"
    assert task_queue.next_task(service, other, {})["task"]["id"] == task["taskId"]


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def test_green_report_needs_a_commit_in_the_source_repo(service, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "a.txt").write_text("a", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "a")
    head = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(task_queue, "source_root", lambda *args: repo)
    task = create(service, "Úkol")
    session = worker(service)
    task_queue.next_task(service, session, {})
    green = {"taskId": task["taskId"], "summary": "s", "checks": GREEN}
    with pytest.raises(GateError) as caught:
        task_queue.report(service, session, {**green, "sha": "0000000"})
    assert caught.value.status == 422 and caught.value.code == "sha_unknown" and "git rev-parse HEAD" in caught.value.hint
    assert service.db_for("draft").execute("SELECT COUNT(*) FROM check_runs").fetchone()[0] == 0
    # červené hlášení práci commitnutou mít nemusí
    assert task_queue.report(service, session, {**green, "sha": "0000000", "checks": RED})["task"]["status"] == "ready"
    task_queue.next_task(service, session, {})
    assert task_queue.report(service, session, {**green, "sha": head[:9]})["task"]["status"] == "done"


def test_sha_is_accepted_without_a_git_source(service, tmp_path, monkeypatch):
    assert task_queue.commit_exists(tmp_path, "0000000") is None  # není repo gitu
    monkeypatch.setattr(task_queue, "source_root", lambda *args: tmp_path)
    task = create(service, "Úkol")
    session = worker(service)
    task_queue.next_task(service, session, {})
    assert report(service, session, task["taskId"], GREEN)["task"]["status"] == "done"


DEFERRED = [{"name": "npm test", "status": "deferred"}]


def sprint_task(service, title, sprint, order=0):
    payload = {"project": "draft", "workspace": "draft", "title": title, "order": order,
               "body": {"do": title, "sprint": sprint}}
    return task_queue.create(service, payload, created_by="heart")


def test_task_body_keeps_a_valid_sprint_and_refuses_bad_shapes():
    body = task_body({"do": "x", "sprint": {"id": " S1 ", "goal": "Základ.", "milestone": ["npm test projde"]}})
    assert body["sprint"] == {"id": "S1", "goal": "Základ.", "milestone": ["npm test projde"]}
    assert "sprint" not in task_body({"do": "x"})  # úkol bez sprintu má tělo jako dřív
    for sprint in ({}, {"id": ""}, {"id": "x" * 41}, {"id": "S1", "goal": 1}, {"id": "S1", "milestone": "a"},
                   {"id": "S1", "who": "?"}, "S1"):
        with pytest.raises(GateError) as caught:
            task_body({"do": "x", "sprint": sprint})
        assert caught.value.code == "invalid_payload" and "sprint" in caught.value.hint


def test_next_marks_the_checkpoint_and_counts_the_sprint(service):
    first = sprint_task(service, "Základ", {"id": "S1", "goal": "Web stojí.", "milestone": ["npm run build projde"]})
    last = sprint_task(service, "Patička", {"id": "S1"})
    loose = create(service, "Bez sprintu")
    session = worker(service)
    got = task_queue.next_task(service, session, {})["task"]
    assert got["id"] == first["taskId"] and got["checkpoint"] is False
    assert got["sprint"] == {"id": "S1", "goal": "Web stojí.", "milestone": ["npm run build projde"], "done": 0,
                             "total": 2}
    assert report(service, session, first["taskId"], DEFERRED)["task"]["status"] == "done"
    got = task_queue.next_task(service, session, {})["task"]
    assert got["id"] == last["taskId"] and got["checkpoint"] is True and got["sprint"]["done"] == 1
    assert report(service, session, last["taskId"], GREEN)["task"]["status"] == "done"
    got = task_queue.next_task(service, session, {})["task"]
    assert got["id"] == loose["taskId"] and got["checkpoint"] is True and got["sprint"] is None
    # odložené kontroly se do check_runs nepíšou
    runs = service.db_for("draft").execute("SELECT scope_id, status FROM check_runs ORDER BY recorded_at").fetchall()
    assert [tuple(row) for row in runs] == [(last["taskId"], "green")]


def test_a_later_task_of_the_sprint_moves_the_checkpoint(service):
    held = sprint_task(service, "Jediný", {"id": "S1"})
    session = worker(service)
    assert task_queue.next_task(service, session, {})["task"]["checkpoint"] is True
    later = sprint_task(service, "Doplněný", {"id": "S1"})
    other = sprint_task(service, "Jiný sprint", {"id": "S2"})
    got = task_queue.next_task(service, session, {})["task"]
    assert got["id"] == held["taskId"] and got["checkpoint"] is False and got["sprint"]["total"] == 2
    task_queue.cancel(service, "draft", later["taskId"], by="heart")
    assert task_queue.next_task(service, session, {})["task"]["checkpoint"] is True
    assert other["body"]["sprint"] == {"id": "S2"}


def test_checkpoint_cannot_defer_checks_and_red_goes_back_to_ready(service):
    sprint_task(service, "Úkol", {"id": "S1"})
    loose = create(service, "Bez sprintu")
    session = worker(service)
    task = task_queue.next_task(service, session, {})["task"]
    for checks in (DEFERRED, GREEN + DEFERRED):
        with pytest.raises(GateError) as caught:
            report(service, session, task["id"], checks)
        assert caught.value.status == 422 and caught.value.code == "checkpoint_needs_checks" and caught.value.hint
    assert service.db_for("draft").execute("SELECT COUNT(*) FROM check_runs").fetchone()[0] == 0
    assert report(service, session, task["id"], RED)["task"] == {"id": task["id"], "status": "ready", "attempts": 1}
    assert report(service, session, task_queue.next_task(service, session, {})["task"]["id"], GREEN)["task"]["status"] == "done"
    assert task_queue.next_task(service, session, {})["task"]["id"] == loose["taskId"]
    with pytest.raises(GateError) as caught:  # úkol bez sprintu je kontrolním bodem vždy
        report(service, session, loose["taskId"], DEFERRED)
    assert caught.value.code == "checkpoint_needs_checks"


def test_non_checkpoint_mixes_deferred_with_real_checks(service):
    first = sprint_task(service, "A", {"id": "S1"}, order=1)
    sprint_task(service, "B", {"id": "S1"}, order=2)
    session = worker(service)
    assert task_queue.next_task(service, session, {})["task"]["id"] == first["taskId"]
    assert report(service, session, first["taskId"], RED + DEFERRED)["task"]["status"] == "ready"
    assert task_queue.next_task(service, session, {})["task"]["id"] == first["taskId"]
    assert report(service, session, first["taskId"], GREEN + DEFERRED)["task"]["status"] == "done"
    outcome = task_queue.list_tasks(service, "draft", "draft", "done")["tasks"][0]["report"]
    assert outcome["checks"] == GREEN + DEFERRED  # hlášení drží i odložené kontroly


def test_deferred_only_report_checks_the_sha_like_a_green_one(service, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "a.txt").write_text("a", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "a")
    monkeypatch.setattr(task_queue, "source_root", lambda *args: repo)
    first = sprint_task(service, "A", {"id": "S1"})
    sprint_task(service, "B", {"id": "S1"})
    session = worker(service)
    task_queue.next_task(service, session, {})
    body = {"taskId": first["taskId"], "summary": "s", "checks": DEFERRED}
    with pytest.raises(GateError) as caught:
        task_queue.report(service, session, {**body, "sha": "0000000"})
    assert caught.value.code == "sha_unknown"
    head = git(repo, "rev-parse", "HEAD")
    assert task_queue.report(service, session, {**body, "sha": head[:9]})["task"]["status"] == "done"
