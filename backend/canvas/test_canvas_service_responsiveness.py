import concurrent.futures
import threading

from backend.canvas.canvas_service import CanvasService


def test_slow_git_view_does_not_block_bootstrap(tmp_path, monkeypatch):
    service = CanvasService(tmp_path / "data")
    service.register_repository(
        "fixture", "Fixture", str(tmp_path / "repo"), "fixture://local", "main"
    )
    entered = threading.Event()
    release = threading.Event()

    def slow_git(root, *args, **kwargs):
        if args == ("rev-parse", "HEAD"):
            entered.set()
            release.wait(3)
            return "a" * 40
        if args == ("branch", "--show-current"):
            return "main"
        return None if kwargs.get("optional") else ""

    monkeypatch.setattr("backend.canvas.canvas_service.git", slow_git)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        source = pool.submit(service.view, "fixture", "main")
        assert entered.wait(1)
        bootstrap = pool.submit(service.bootstrap)
        try:
            assert bootstrap.result(timeout=0.3)["projects"][0]["id"] == "fixture"
        finally:
            release.set()
            source.result(timeout=3)
