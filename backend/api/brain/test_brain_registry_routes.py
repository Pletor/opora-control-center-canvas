import sqlite3
import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.brain.brain_registry_routes import create_brain_registry_router
from backend.brain import seed
from database.schema.project_schema import REGISTRY_SCHEMA


def test_artifacts_list_and_detail_with_versions(tmp_path):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    seed.ensure(db, tmp_path, ponytail_cache=tmp_path / "chybi")
    app = FastAPI()
    app.include_router(create_brain_registry_router(SimpleNamespace(db=db, registry_lock=threading.RLock())))
    client = TestClient(app)
    artifacts = client.get("/api/brain-registry/artifacts").json()["artifacts"]
    assert [item["id"] for item in artifacts] == ["opora:brain:skill:heart", "opora:brain:skill:vyslech"]
    pin = artifacts[0]["active"]["pin"]
    assert pin.startswith("opora:brain:skill:heart@") and len(pin.split("@")[1]) == 12
    detail = client.get("/api/brain-registry/artifacts/opora:brain:skill:heart").json()
    assert detail["active"]["pin"] == pin and [v["status"] for v in detail["versions"]] == ["active"]
    assert detail["versions"][0]["links"] == []
    assert client.get("/api/brain-registry/artifacts/opora:brain:skill:nic").status_code == 404
