import json
from backend.editor.storyboard.storyboard_export import export_workspace
from backend.editor.storyboard.test_storyboard import service, board, payload


def test_export_latest_working_data_preserves_history_and_old_files(service, tmp_path):
    path = service._path("draft", "draft", "karta")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({**board(), "revision": 4})
    path.write_text(raw, encoding="utf-8")
    service.read("draft", "draft", "karta")
    service.save(payload(board(title="New SQL working scene"), revision=4))
    before = service.canvas.db_for("draft").total_changes
    destination = tmp_path / "rollback-export"
    manifest = export_workspace(service.canvas, "draft", "draft", destination)
    assert manifest == [{"project": "draft", "workspace": "draft", "nodeId": "karta", "revision": 5, "filePresent": True}]
    assert service.canvas.db_for("draft").total_changes == before
    assert path.read_text(encoding="utf-8") == raw
    exported = json.loads((destination / "karta.json").read_text(encoding="utf-8"))
    assert exported["title"] == "New SQL working scene" and exported["revision"] == 5
    assert service.read("draft", "draft", "karta", 4)["revision"] == 4


def test_historical_scene_remains_readable_after_card_removed(service):
    service.save(payload(board(title="Historical contract")))
    view = service.canvas.view("draft", "draft")
    graph = {**view["graph"], "nodes": [node for node in view["graph"]["nodes"] if node["id"] != "karta"]}
    service.canvas.save_graph("draft", "draft", graph, view["digest"], allow_removal=True)
    assert service.read("draft", "draft", "karta", 1)["storyboard"]["title"] == "Historical contract"
