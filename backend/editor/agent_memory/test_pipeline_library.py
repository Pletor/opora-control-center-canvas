"""Knihovna pipeline: verzovaný JSON v library/, čtený přes GET; žádná demo data v komponentě."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory import pipeline_library
from backend.paths import REPO_ROOT

ORIGIN = "http://127.0.0.1:8740"


def test_library_file_exists_and_every_pipeline_has_unique_id_label_description():
    library = pipeline_library.load()
    assert library["categories"], "knihovna má aspoň jednu kategorii"
    ids = []
    for category in library["categories"]:
        assert category["id"] and category["label"]
        assert category["pipelines"], f"kategorie {category['id']} nemá pipeline"
        for item in category["pipelines"]:
            assert item["id"] and item["label"] and item["description"]
            ids.append(item["id"])
    assert len(ids) == len(set(ids))


def test_invalid_library_file_is_reported_not_guessed(tmp_path):
    broken = tmp_path / "pipelines.json"
    broken.write_text(json.dumps({"categories": [{"id": "x"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        pipeline_library.load(broken)


def test_endpoint_returns_the_library_and_is_read_only(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        response = client.get("/api/desktop-v3/pipelines")
        assert response.status_code == 200, response.text
        expected = json.loads((REPO_ROOT / "library" / "pipelines.json").read_text(encoding="utf-8"))
        assert response.json() == expected
        assert client.post("/api/desktop-v3/pipelines", headers={"origin": ORIGIN}, json={}).status_code in (403, 405)
