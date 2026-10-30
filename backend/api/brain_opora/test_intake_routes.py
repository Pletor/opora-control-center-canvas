"""`GET /api/intake` přes skutečnou aplikaci: oblasti, poslední vstupy a počty; jen čtení, chyby rozsahu 404 / 422."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import intake
from backend.canvas.test_canvas_plan import ORIGIN


def test_intake_view_reads_entries_and_refuses_unknown_scope(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/intake", params={"project": "draft", "workspace": "draft"}).json() == {
            "areas": [], "entries": [], "pending": 0, "duplicates": 0}
        db = app.state.service.db_for("draft")
        with db:
            intake.record(db, "draft", "heart_message", None, "Přidej hledání.", "2026-10-30T10:00:00Z")
            intake.record(db, "draft", "gate_ask", "gt_1", "přidej hledání", "2026-10-30T10:01:00Z")
        body = client.get("/api/intake", params={"project": "draft", "workspace": "draft"}).json()
        assert (body["pending"], body["duplicates"]) == (1, 1)
        assert [(entry["source"], entry["verdict"]) for entry in body["entries"]] == [
            ("gate_ask", "duplicate"), ("heart_message", "pending")]
        assert body["entries"][0]["sourceRef"] == "gt_1" and body["entries"][0]["layer"] == "determinism"
        for params, status in (({"project": "nikde", "workspace": "draft"}, 404),
                               ({"project": "draft"}, 422), ({"project": "draft", "workspace": "w-neni"}, 404)):
            assert client.get("/api/intake", params=params).status_code == status
