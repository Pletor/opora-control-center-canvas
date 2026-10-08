"""Čtení historie nesmí opakovaně dekódovat snapshoty ani blokovat plátno."""
import threading

from backend.canvas.canvas_service import CanvasService
from backend.editor.canvas_versions.canvas_versions import CanvasVersions
import backend.editor.canvas_versions.canvas_versions as module


def test_warm_history_reuses_summaries_and_write_invalidates(tmp_path, monkeypatch):
    service = CanvasService(tmp_path)
    try:
        versions = CanvasVersions(service)
        payload = {"project": "draft", "workspace": "draft", "digest": service.view("draft", "draft")["digest"], "author": "Test"}
        versions.save(payload)
        original = module._summary
        calls = []
        def summary(row):
            calls.append(row["id"])
            return original(row)
        monkeypatch.setattr(module, "_summary", summary)
        first = versions.list("draft", "draft")
        assert versions.list("draft", "draft") == first
        assert len(calls) == 1
        versions.save(payload)
        assert len(versions.list("draft", "draft")["versions"]) == 2
    finally:
        service.close()


def test_history_decode_does_not_hold_canvas_locks(tmp_path, monkeypatch):
    service = CanvasService(tmp_path)
    try:
        versions = CanvasVersions(service)
        versions.save({"project": "draft", "workspace": "draft", "digest": service.view("draft", "draft")["digest"], "author": "Test"})
        original = module._summary
        def summary(row):
            acquired = []
            def probe():
                for lock in (service.graph_lock, service.lock):
                    ok = lock.acquire(timeout=.2)
                    acquired.append(ok)
                    if ok:
                        lock.release()
            thread = threading.Thread(target=probe)
            thread.start()
            thread.join(timeout=1)
            assert acquired == [True, True]
            return original(row)
        monkeypatch.setattr(module, "_summary", summary)
        versions.list("draft", "draft")
    finally:
        service.close()
