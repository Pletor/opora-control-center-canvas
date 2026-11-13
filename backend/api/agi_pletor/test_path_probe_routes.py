"""`/api/pletor/path-probe`: agent spustí a dozví se, že pískoviště zakládá člověk; člověk projde zeleně; text čte agent."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=t"}
PATH = "/api/pletor/path-probe"


def test_agent_run_stops_on_the_human_step_and_human_run_is_green(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        assert client.get(PATH).json() == {"last": None}
        stopped = client.post(PATH, headers=AGENT, json={})
        assert stopped.status_code == 200 and stopped.json()["steps"][0]["status"] == "human", stopped.text
        text = client.get(PATH, params={"format": "text"}).text.splitlines()
        assert text[0].startswith("PRŮCHOD CESTY: stojí na kroku projekt") and len(text) == 8
        green = client.post(PATH, headers=HEADERS, json={}, params={"format": "text"})
        assert green.status_code == 200 and green.text.startswith("PRŮCHOD CESTY: zelený"), green.text
        assert client.get(PATH).json()["last"]["ok"] is True
        client.cookies.clear()
        assert client.post(PATH, headers=HEADERS, json={}).status_code == 428
