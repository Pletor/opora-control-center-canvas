"""Velín V2/V3 s falešnými zdroji: tvar srdce, fronta po prostorech, výpadek zdroje jako `{error}`, filtr rozhovoru."""
import sqlite3
import threading
from types import SimpleNamespace

from backend.agi_pletor import store
from backend.agi_pletor.dashboard import views
from backend.agi_pletor.dashboard.heart_view import heart_view


class Heart:
    def __init__(self, error=None):
        self.error, self.lock = error, threading.Lock()
        self.pending = {"p": [("main", {}, 0), ("main", {}, 0), ("web", {}, 0)]}

    def status(self, project):
        if self.error:
            raise self.error
        return {"running": False, "pending": 3, "sleeping": True, "sleepingUntil": "2026-11-05T10:00:00Z",
                "nextAllowedAt": None, "error": None, "idleReason": "waiting_human", "session": {"batches": 1},
                "batches": [{"id": "b1", "startedAt": "t0", "summary": "Hero.", "costUsd": 0.1, "extra": 1}]}


def service_with_brain(active=True):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE brain_artifact_versions(artifact_id, version, status, created_at)")
    if active:
        db.execute("INSERT INTO brain_artifact_versions VALUES('opora:brain:skill:heart','abc','active','2026-11-05')")
    return SimpleNamespace(db=db, registry_lock=threading.RLock())


def test_heart_view_shape():
    view = heart_view(service_with_brain(), Heart(), "p", "main")
    assert view["status"]["sleeping"] is True and view["status"]["sleepingUntil"] == "2026-11-05T10:00:00Z"
    assert view["status"]["lastSummary"] == "Hero." and "batches" not in view["status"]
    assert view["queue"] == [{"workspace": "main", "pending": 2}, {"workspace": "web", "pending": 1}]
    assert view["batches"] == [{"id": "b1", "startedAt": "t0", "summary": "Hero.", "costUsd": 0.1}]
    assert view["gate"] is False and view["brain"] == {"version": "abc", "activatedAt": "2026-11-05"}
    assert heart_view(service_with_brain(False), Heart(), "p", "main")["brain"] is None


def test_failing_source_becomes_error_section():
    view = heart_view(service_with_brain(), Heart(error=RuntimeError("spí")), "p", "main")
    assert view["status"] == {"error": "spí"} and view["batches"] == {"error": "spí"}
    assert view["queue"][0]["pending"] == 2


def test_messages_view_filters_and_limits(tmp_path):
    for index, text in enumerate(["Ahoj", "Dvě stránky", "STRÁNKY hotové"]):
        store.append_message(tmp_path, f"t{index}", "p", "main", "human", text)
    store.append_message(tmp_path, "x", "p", "jiny", "human", "stránky jinde")
    assert views.messages_view(tmp_path, "p", "main")["total"] == 3
    found = views.messages_view(tmp_path, "p", "main", limit=1, q="stránky")
    assert found["total"] == 2 and [m["text"] for m in found["messages"]] == ["STRÁNKY hotové"]
