"""Actual factory token/human boundaries and immutable attachment download."""
import pytest

from backend.api.brain_opora.test_canvas_capability_routes import ORIGIN
from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.project.site_admin import proposal_attachments as files
from backend.project.site_admin import store
from backend.project.site_admin.test_proposal_attachments import PNG, put


@pytest.fixture
def attachment_setup(tmp_path):
    yield from capability_setup.__wrapped__(tmp_path)


def test_token_stages_scoped_download_and_only_human_accepts(attachment_setup):
    client, service, auth = attachment_setup
    reply = client.post("/api/site-admin/proposals", headers=auth,
                        json={"project": "draft", "changes": {}, "attachments": [put()]})
    assert reply.status_code == 200, reply.text
    proposal = reply.json()
    assert proposal["diff"] == [] and proposal["attachments"][0]["sha256"] == files.digest(PNG)
    route = f"/api/site-admin/proposals/{proposal['id']}/attachments/0"
    blob = client.get(route, params={"project": "draft"}, headers=auth)
    assert blob.status_code == 200, blob.text
    assert blob.content == PNG and blob.headers["content-type"] == "application/octet-stream"
    assert blob.headers["content-disposition"].startswith("attachment;") and blob.headers["x-content-type-options"] == "nosniff"
    assert client.get(route, params={"project": "foreign"}, headers=auth).status_code == 403
    ui_cookies = dict(client.cookies)
    client.cookies.clear()
    assert client.get(route, params={"project": "draft"}, headers={"X-Opora-Actor": "human"}).status_code == 428
    assert files.read(service, "draft", "assets/logos/logo.png") is None
    accept = f"/api/site-admin/proposals/{proposal['id']}/accept"
    body = {"project": "draft", "expectedRevision": 0}
    assert client.post(accept, json=body, headers=auth).status_code == 403
    client.cookies.update(ui_cookies)
    response = client.post(accept, json=body, headers={"origin": ORIGIN, "X-Opora-Actor": "human"})
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 1 and files.read(service, "draft", "assets/logos/logo.png") == PNG
    assert client.post(accept, json=body, headers={"origin": ORIGIN, "X-Opora-Actor": "human"}).json() == response.json()


def test_interrupted_http_accept_reports_actual_targets_and_resumes(attachment_setup, monkeypatch):
    client, service, auth = attachment_setup
    proposal = client.post("/api/site-admin/proposals", headers=auth,
                           json={"project": "draft", "changes": {}, "attachments": [put(), put("second.png", PNG + b"2")]}).json()
    client.get("/api/access/ui-session", headers={"origin": ORIGIN})
    human = {"origin": ORIGIN, "X-Opora-Actor": "human"}
    original = files.write
    def crash(service, project, path, raw):
        if path == "assets/logos/second.png":
            raise OSError("Injected")
        return original(service, project, path, raw)
    monkeypatch.setattr(files, "write", crash)
    accept = f"/api/site-admin/proposals/{proposal['id']}/accept"
    response = client.post(accept, headers=human, json={"project": "draft", "expectedRevision": 0})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "site_recovery_needed"
    pending = client.get("/api/site-admin/proposals", params={"project": "draft"}).json()["proposals"][0]
    assert pending["recoveryNeeded"] and pending["recoveryTargets"][0]["state"] == "after"
    monkeypatch.setattr(files, "write", original)
    assert client.post(accept, headers=human, json={"project": "draft", "expectedRevision": 0}).status_code == 200
    assert store.read(service, "draft")["revision"] == 1


def test_http_stages_larger_than_old_body_limit_and_rejects_native_overflow(attachment_setup, monkeypatch):
    client, service, auth = attachment_setup
    large = PNG + b"x" * (2 * 1024 * 1024)
    body = {"project": "draft", "changes": {}, "attachments": [put("large.png", large)]}
    response = client.post("/api/site-admin/proposals", headers=auth, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["attachments"][0]["size"] == len(large)
    assert files.read(service, "draft", "assets/logos/large.png") is None
    oversized = {**body, "attachments": [put("huge.png", PNG + b"x" * store.ASSET_LIMIT)]}
    assert client.post("/api/site-admin/proposals", headers=auth, json=oversized).status_code == 422
    monkeypatch.setattr(files, "BUNDLE_BYTES", len(large))
    bundle = {**body, "attachments": [put("one.png", large), put("two.png", large)]}
    assert client.post("/api/site-admin/proposals", headers=auth, json=bundle).status_code == 422
