from backend.service import CanvasService


def test_main_graph_is_pinned_to_reported_sha(tmp_path, monkeypatch):
    service = CanvasService(tmp_path / "data")
    service.register_repository(
        "fixture", "Fixture", str(tmp_path / "repo"), "fixture://local", "main"
    )
    calls = []

    def snapshot_git(root, *args, **kwargs):
        calls.append(args)
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("branch", "--show-current"):
            return "main"
        return None if kwargs.get("optional") else ""

    monkeypatch.setattr("backend.service.git", snapshot_git)
    snapshot = service.view("fixture", "main")
    assert ("show", snapshot["sha"] + ":opora-canvas.json") in calls
