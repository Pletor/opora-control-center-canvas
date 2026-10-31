"""Fronta úkolů: pořadí `seq`, přidělení jedné relaci, výsledek hlášení, zrušení a návrat úkolů prošlých relací."""
import sqlite3

import pytest

from database.repositories.heart_tasks import HeartTaskStore
from database.schema.project_initialization import initialize_project_schema

AT = "2026-10-29T10:00:00Z"
LATER = "2026-10-29T20:00:00Z"


@pytest.fixture
def store():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    yield HeartTaskStore(connection, "p1")
    connection.close()


def session(store, session_id, expires_at="2026-10-29T18:00:00Z", revoked_at=None):
    store.db.execute("INSERT INTO gate_sessions VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (session_id, "p1", "main", "worker", "dev", "{}", "h_" + session_id, AT, expires_at, revoked_at))


def test_insert_list_and_oldest_ready(store):
    store.insert("ht_1", "main", "n1", "První", {"do": "a"}, "human", AT)
    store.insert("ht_2", "main", None, "Druhý", {"do": "b"}, "human", AT)
    store.insert("ht_3", "w2", None, "Jinde", {"do": "c"}, "human", AT)
    task = store.get("ht_1")
    assert task["status"] == "ready" and task["body"] == {"model": "sonnet", "do": "a"} and task["nodeId"] == "n1"
    assert task["attempts"] == 0 and task["sessionId"] is None and task["report"] is None
    assert [t["taskId"] for t in store.list("main")] == ["ht_1", "ht_2"]
    assert store.oldest_ready("main")["taskId"] == "ht_1"
    assert HeartTaskStore(store.db, "p2").list("main") == []


def test_assign_once_and_held_by(store):
    store.insert("ht_1", "main", None, "Úkol", {"do": "a"}, "human", AT)
    assert store.assign("ht_1", "gs_1", AT) is True
    assert store.assign("ht_1", "gs_2", AT) is False
    assert store.held_by("gs_1")["taskId"] == "ht_1" and store.held_by("gs_2") is None
    assert [t["taskId"] for t in store.list("main", "assigned")] == ["ht_1"]


def test_finish_red_returns_to_ready_and_only_holder_finishes(store):
    store.insert("ht_1", "main", None, "Úkol", {"do": "a"}, "human", AT)
    store.assign("ht_1", "gs_1", AT)
    assert store.finish("ht_1", "gs_2", "done", 0, {}, AT) is False
    assert store.finish("ht_1", "gs_1", "ready", 1, {"sha": "abc1234"}, AT) is True
    task = store.get("ht_1")
    assert (task["status"], task["sessionId"], task["attempts"]) == ("ready", None, 1)
    assert task["report"] == {"sha": "abc1234"}
    store.assign("ht_1", "gs_1", AT)
    assert store.finish("ht_1", "gs_1", "done", 1, {}, AT) is True
    assert store.get("ht_1")["status"] == "done"


def test_release_returns_only_the_holders_task_and_keeps_attempts(store):
    store.insert("ht_1", "main", None, "Úkol", {"do": "a"}, "human", AT)
    assert store.release("ht_1", "gs_1", AT) is False  # ready, nikdo ho nedrží
    store.assign("ht_1", "gs_1", AT)
    store.finish("ht_1", "gs_1", "ready", 1, {}, AT)
    store.assign("ht_1", "gs_1", AT)
    assert store.release("ht_1", "gs_2", LATER) is False
    assert store.release("ht_1", "gs_1", LATER) is True
    task = store.get("ht_1")
    assert (task["status"], task["sessionId"], task["attempts"], task["updatedAt"]) == ("ready", None, 1, LATER)


def test_cancel_only_open_tasks(store):
    store.insert("ht_1", "main", None, "Úkol", {"do": "a"}, "human", AT)
    assert store.cancel("ht_1", AT) is True and store.cancel("ht_1", AT) is False
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("UPDATE heart_tasks SET status='lost'")


def test_reclaim_tasks_of_expired_or_revoked_sessions(store):
    session(store, "gs_live", expires_at="2026-10-30T10:00:00Z")
    session(store, "gs_old")
    session(store, "gs_gone", revoked_at=AT)
    for number, holder in enumerate(("gs_live", "gs_old", "gs_gone")):
        store.insert(f"ht_{number}", "main", None, "Úkol", {"do": "a"}, "human", AT)
        store.assign(f"ht_{number}", holder, AT)
    assert store.reclaim(LATER) == ["ht_1", "ht_2"]
    assert [t["status"] for t in store.list("main")] == ["assigned", "ready", "ready"]
    assert store.reclaim(LATER) == []


def test_order_goes_first_then_seq(store):
    store.insert("ht_1", "main", None, "Bez pořadí", {"do": "a"}, "human", AT)
    store.insert("ht_2", "main", None, "Druhý krok", {"do": "b"}, "heart", AT, order=2)
    store.insert("ht_3", "main", None, "První krok", {"do": "c"}, "heart", AT, order=1)
    store.insert("ht_4", "main", None, "Také první", {"do": "d"}, "heart", AT, order=1)
    assert store.get("ht_2")["order"] == 2 and store.get("ht_1")["order"] == 0
    picked = []
    while (ready := store.oldest_ready("main")) is not None:
        picked.append(ready["taskId"])
        store.assign(ready["taskId"], "gs_1", AT)
    assert picked == ["ht_1", "ht_3", "ht_4", "ht_2"]


def test_order_column_is_added_to_a_table_from_h1b():
    from database.repositories.heart_tasks import ensure_order_column
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE heart_tasks(seq INTEGER PRIMARY KEY, id TEXT)")
    connection.execute("INSERT INTO heart_tasks VALUES(1, 'ht_old')")
    ensure_order_column(connection)
    ensure_order_column(connection)
    assert connection.execute("SELECT task_order FROM heart_tasks").fetchone()[0] == 0
    connection.close()


def test_in_sprints_lists_tasks_of_sprints_in_queue_order(store):
    store.insert("ht_1", "main", None, "Bez sprintu", {"do": "a"}, "human", AT)
    store.insert("ht_2", "main", None, "S1 druhý", {"do": "b", "sprint": {"id": "S1"}}, "heart", AT, order=2)
    store.insert("ht_3", "main", None, "S1 první", {"do": "c", "sprint": {"id": "S1", "goal": "g"}}, "heart", AT, order=1)
    store.insert("ht_4", "main", None, "S2", {"do": "d", "sprint": {"id": "S2"}}, "heart", AT)
    store.insert("ht_5", "w2", None, "Jinde", {"do": "e", "sprint": {"id": "S1"}}, "heart", AT)
    assert [t["taskId"] for t in store.in_sprints("main")] == ["ht_4", "ht_3", "ht_2"]
    assert [t["taskId"] for t in store.in_sprints("main", "S1")] == ["ht_3", "ht_2"]
    assert store.in_sprints("main", "S9") == [] and HeartTaskStore(store.db, "p2").in_sprints("main") == []
