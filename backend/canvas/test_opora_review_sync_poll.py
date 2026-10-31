"""The server enqueues review jobs on its own pass, without any worker claim."""
import threading

from backend.canvas.opora_review_sync_poll import poll
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import config, use
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401


class Manager:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def manager_of(review):  # noqa: F811
    workspace = review["scope"]["workspace"]
    return Manager(clock=lambda: 0, stop=threading.Event(), review_jobs=review["jobs"],
                           _workspaces=lambda project, sql, *params: [workspace])


def test_one_pass_creates_jobs_without_a_worker_claim(review, monkeypatch):  # noqa: F811
    monkeypatch.setenv("OPORA_REVIEW_SYNC_SECONDS", "0")
    use(review, config())
    assert review["jobs"].list(**review["scope"])["jobs"] == []
    created = poll(manager_of(review), review["scope"]["project"])
    assert created and {job["kind"] for job in review["jobs"].list(**review["scope"])["jobs"]} >= {"code"}
    assert poll(manager_of(review), review["scope"]["project"]) == []  # idempotent


def test_disabled_review_never_calls_sync(review, monkeypatch):  # noqa: F811
    monkeypatch.setenv("OPORA_REVIEW_SYNC_SECONDS", "0")
    use(review, {**config(), "enabled": False})
    review["jobs"].sync = lambda *_: (_ for _ in ()).throw(AssertionError("sync called"))
    assert poll(manager_of(review), review["scope"]["project"]) == []
