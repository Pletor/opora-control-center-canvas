import io
import sqlite3
import threading
import zipfile
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.brain.brain_registry_routes import create_brain_registry_router
from backend.brain import registry, seed
from database.schema.project_schema import REGISTRY_SCHEMA


def client_for(tmp_path):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    seed.ensure(db, tmp_path, ponytail_cache=tmp_path / "chybi")
    app = FastAPI()
    app.include_router(create_brain_registry_router(SimpleNamespace(db=db, registry_lock=threading.RLock(),
                                                                    root=tmp_path)))
    return db, TestClient(app)


def test_artifacts_list_and_detail_with_versions(tmp_path):
    _, client = client_for(tmp_path)
    artifacts = client.get("/api/brain-registry/artifacts").json()["artifacts"]
    assert [item["id"] for item in artifacts] == ["opora:brain:skill:heart", "opora:brain:skill:vyslech"]
    pin = artifacts[0]["active"]["pin"]
    assert pin.startswith("opora:brain:skill:heart@") and len(pin.split("@")[1]) == 12
    detail = client.get("/api/brain-registry/artifacts/opora:brain:skill:heart").json()
    assert detail["active"]["pin"] == pin and [v["status"] for v in detail["versions"]] == ["active"]
    assert detail["versions"][0]["links"] == []
    assert client.get("/api/brain-registry/artifacts/opora:brain:skill:nic").status_code == 404


def test_pin_zip_is_the_plugin_root_and_unknown_version_is_404(tmp_path):
    db, client = client_for(tmp_path)
    short = registry.active(db, "opora:brain:skill:heart")["version"][:12]
    response = client.get(f"/api/brain-registry/pins/opora-heart@{short}.zip")
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert {".claude-plugin/plugin.json", "skills/heart/SKILL.md", "skills/vyslech/SKILL.md"} <= set(names)
    assert (tmp_path / "brain-pins" / f"opora-heart@{short}.zip").is_file()  # vytvořený přes Store.export
    for name in ("opora-heart@" + "0" * 12, f"ponytail@{short}", f"Opora@{short}", f"opora-heart@{short[:7]}"):
        assert client.get(f"/api/brain-registry/pins/{name}.zip").status_code == 404, name


def test_pin_zip_through_the_public_tunnel_needs_the_access_token(tmp_path, monkeypatch):
    from backend.app.factory import create_app

    monkeypatch.setenv("OPORA_PUBLIC_HOSTS", "*.trycloudflare.com")
    monkeypatch.setenv("OPORA_ACCESS_TOKEN", "z" * 32)
    route = "/api/brain-registry/pins/ponytail@" + "a" * 12 + ".zip"
    app = create_app(tmp_path / "data")
    tunnel = TestClient(app, base_url="https://abc.trycloudflare.com")
    assert tunnel.get(route).status_code == 401
    assert tunnel.get(route, headers={"authorization": "Bearer " + "z" * 32}).status_code == 404  # token pustí
    assert TestClient(app, base_url="http://127.0.0.1:8740").get(route).status_code == 404  # loopback bez tokenu
