from fastapi.testclient import TestClient

from backend.app import create_app


def test_empty_application_and_origin_gate(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        r = client.get("/api/bootstrap")
        assert r.status_code == 200 and r.json()["projects"] == []
        assert client.get("/api/view?project=draft&workspace=draft").json()["graph"]["nodes"] == []
        assert (
            client.post(
                "/api/connect",
                json={"url": "https://github.com/x/y", "approved": True},
                headers={"origin": "https://evil.test"},
            ).status_code
            == 403
        )
        assert client.get("/api/bootstrap", headers={"host": "evil.test"}).status_code == 403
        assert (
            client.post(
                "/api/connect",
                json={"url": "https://github.com/x/y", "approved": False},
                headers={"origin": "http://127.0.0.1:8740"},
            ).status_code
            == 409
        )
