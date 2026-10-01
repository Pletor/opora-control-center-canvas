import json
import threading

from backend.claude_code.assistant.registry import DEFAULT_TITLE, SessionRegistry, title_from


def test_create_persists_atomically(tmp_path):
    registry = SessionRegistry(tmp_path)
    record = registry.create("p1", "draft", "opus")
    path = tmp_path / "assistant" / "sessions.json"
    assert path.exists() and not path.with_suffix(".json.tmp").exists()
    saved = json.loads(path.read_text(encoding="utf-8"))["sessions"][0]
    assert set(saved) == {"id", "projectId", "workspace", "title", "model", "claudeSessionId",
                          "createdAt", "updatedAt", "state", "nodeId"}
    assert saved["title"] == DEFAULT_TITLE and saved["state"] == "idle" and saved["nodeId"] is None
    assert registry.create("p1", "draft", "opus", title="  Plán  ")["title"] == "Plán"
    assert record["id"] == saved["id"]


def test_running_becomes_idle_after_restart(tmp_path):
    registry = SessionRegistry(tmp_path)
    first = registry.create("p1", "main", "sonnet")
    registry.update(first["id"], state="running", claudeSessionId="abc")
    again = SessionRegistry(tmp_path).get(first["id"])
    assert again["state"] == "idle" and again["claudeSessionId"] == "abc"


def test_list_filters_project_and_closed(tmp_path):
    registry = SessionRegistry(tmp_path)
    a = registry.create("p1", "draft", "opus")
    b = registry.create("p1", "draft", "opus")
    registry.create("p2", "draft", "opus")
    registry.update(b["id"], state="closed")
    assert [item["id"] for item in registry.list("p1")] == [a["id"]]
    assert len(registry.list("p1", include_closed=True)) == 2


def test_update_validates_and_is_thread_safe(tmp_path):
    registry = SessionRegistry(tmp_path)
    record = registry.create("p1", "draft", "opus")
    for bad in ({"state": "weird"}, {"id": "x"}):
        try:
            registry.update(record["id"], **bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)
    assert registry.update("missing", state="idle") is None
    threads = [threading.Thread(target=registry.update, args=(record["id"],), kwargs={"title": f"t{i}"})
               for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert SessionRegistry(tmp_path).get(record["id"])["title"].startswith("t")


def test_title_from_first_message():
    assert title_from("  Ahoj   světe ") == "Ahoj světe"
    assert len(title_from("x" * 100)) == 60
    assert title_from("") == DEFAULT_TITLE


def test_broken_file_starts_empty(tmp_path):
    path = tmp_path / "assistant" / "sessions.json"
    path.parent.mkdir()
    path.write_text("{nejde", encoding="utf-8")
    assert SessionRegistry(tmp_path).list() == []
