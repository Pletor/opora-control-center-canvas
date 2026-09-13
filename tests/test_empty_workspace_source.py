from fastapi.testclient import TestClient
from test_workspace_sources import ORIGIN

from backend.app.factory import create_app


def test_new_project_has_an_empty_managed_source_tree(tmp_path):
    with TestClient(create_app(tmp_path / "appdata"), base_url=ORIGIN) as client:
        created = client.post("/api/empty-project", headers={"Origin": ORIGIN}, json={"name": "Nový v2 projekt", "confirmed": True})
        assert created.status_code == 200
        pid = created.json()["id"]
        tree = client.get("/api/workspace/tree", params={"project": pid, "workspace": "draft"})
        assert tree.status_code == 200
        assert tree.json()["available"] is True, "Nový projekt musí mít skutečný prázdný kořen, ne missing zdroj"
        assert tree.json()["entries"] == [] and tree.json()["total"] == 0
        bootstrap = client.get("/api/bootstrap").json()
        assert any(project["id"] == pid for project in bootstrap["projects"])
