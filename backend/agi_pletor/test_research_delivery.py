from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.agi_pletor.test_service import Runner, pletor_for
from backend.canvas.test_canvas_plan import ORIGIN, seed


def test_failed_research_handoff_is_visible_in_reply_and_stream(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        runner = Runner({"reply": "Zakládám otázku.", "actions": [
            {"type": "heart_question", "text": "Ověř izolaci tenantů."}]})
        pletor = pletor_for(client, runner)
        chunks = []
        reply = pletor.message("draft", "draft", "Prověř přihlášení.", on_delta=chunks.append)
        assert reply["actions"][0]["ok"] is False
        assert "Otázka srdci nebyla předána" in reply["reply"]
        assert "zapnutou bránou" in reply["reply"]
        assert "".join(chunks) == reply["reply"]
        assert pletor.state("draft", "draft")["messages"][-1]["text"] == reply["reply"]
