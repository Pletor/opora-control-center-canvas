"""ETag/304 pro `GET /api/bootstrap`: klient se ptá každé 2,5 s, obsah se mění zřídka.

Beze změny jde 304 bez těla; nový projekt, úloha nebo přepnutá paměť dají jiný ETag a celé tělo.
"""
import re

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
TAG = re.compile(r'^"[0-9a-f]{40}"$')


def read(client, tag=None):
    return client.get("/api/bootstrap", headers={"If-None-Match": tag} if tag else {})


def test_unchanged_bootstrap_answers_304_without_body(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        first = read(client)
        assert first.status_code == 200
        tag = first.headers["etag"]
        assert TAG.match(tag) and first.headers["cache-control"] == "no-store"
        again = read(client, tag)
        assert again.status_code == 304 and again.content == b"" and again.headers["etag"] == tag
        # Seznam, slabý ETag i * odpovídají stejně (RFC 9110); cizí ETag ne.
        assert read(client, f'"x", W/{tag}').status_code == 304
        assert read(client, "*").status_code == 304
        stale = read(client, '"' + "0" * 40 + '"')
        assert stale.status_code == 200 and stale.json() == first.json() and stale.headers["etag"] == tag


def test_bootstrap_tag_changes_with_jobs_and_memory(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        tag = read(client).headers["etag"]
        service = app.state.service
        with service.registry_lock:
            service.db.execute(
                "INSERT INTO jobs(id,kind,status,message,project_id,updated_at) VALUES(?,?,?,?,?,?)",
                ("job-1", "clone", "running", "Běží.", None, "2026-10-23T00:00:00"),
            )
            service.db.commit()
        changed = read(client, tag)
        assert changed.status_code == 200 and changed.headers["etag"] != tag
        assert [job["id"] for job in changed.json()["jobs"]] == ["job-1"]
        jobs_tag = changed.headers["etag"]
        assert read(client, jobs_tag).status_code == 304

        class Memory:
            def bootstrap_status(self):
                return {"enabled": True, "status": "unknown"}

        service.memory_service = Memory()
        toggled = read(client, jobs_tag)
        assert toggled.status_code == 200 and toggled.headers["etag"] != jobs_tag
        assert toggled.json()["memory"] == {"enabled": True, "status": "unknown"}
