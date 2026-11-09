"""Actual HTTP human pairing, two tab isolation and stale/expired acknowledgement fences."""
from backend.api.brain_opora.test_canvas_capability_routes import ORIGIN, SCOPE, call, setup
from backend.brain_opora.canvas_capabilities import view_attachments
from backend.brain_opora.determinism import tokens

__all__ = ["setup"]
BASE = "/api/canvas-view-attachments"


def post(client, action, handle, **extra):
    if action == "ack":
        extra.setdefault("renderEpoch", 0)
    credentials = {key: handle[key] for key in ("sessionId", "attachmentId", "secret") if key in handle}
    return client.post(BASE + "/" + action, headers={"origin": ORIGIN}, json={**SCOPE, **credentials, **extra})


def test_human_pairing_two_tabs_exact_ack_and_no_shared_write(setup):
    client, service, auth = setup
    first = call(client, auth, "session_view.read").json()["sessionId"]
    second, token = tokens.issue_heart(service, "draft", "draft")
    other = {**auth, tokens.HEADER: token}
    before = service.view("draft", "draft")["digest"]
    handles = []
    for session in (first, second):
        response = post(client, "attach", {"sessionId": session})
        assert response.status_code == 200, response.text
        handles.append(response.json())
    a, b = handles
    assert a["secret"] != b["secret"]
    assert post(client, "attach", {"sessionId": first}).status_code == 409
    assert post(client, "poll", {**a, "secret": b["secret"]}).status_code == 409
    requested = {"selection": [], "viewport": {"x": 10, "y": 20, "zoom": 1.1}, "filter": "alpha", "structureCollapsed": ["sectors"]}
    made = call(client, auth, "session_view.update", {"expectedRevision": 0, "view": requested}, "first-view").json()
    assert not made["applied"]
    assert post(client, "ack", a, revision=0, view=requested).status_code == 409
    assert post(client, "ack", a, revision=1, view={**requested, "filter": "wrong"}).status_code == 409
    assert post(client, "ack", a, revision=1, view={**requested, "structureCollapsed": []}).status_code == 409
    assert post(client, "ack", a, revision=1, view=requested).json()["applied"]
    assert call(client, auth, "session_view.read").json()["applied"]
    assert not call(client, other, "session_view.read").json()["applied"]
    assert not post(client, "pending", a).json()["applied"]
    assert post(client, "ack", a, revision=1, view=requested).status_code == 409
    assert service.view("draft", "draft")["digest"] == before
    stored = service.db_for("draft").execute("SELECT secret_hash FROM canvas_view_attachments").fetchall()
    assert a["secret"] not in str(stored) and b["secret"] not in str(stored)


def test_private_structure_groups_native_cas_replay_scope_and_legacy(setup):
    client, service, auth = setup
    view = {"selection": [], "viewport": None, "filter": "", "structureCollapsed": ["areas", "nodes"]}
    body = {"expectedRevision": 0, "view": view}
    made = call(client, auth, "session_view.update", body, "collapse")
    assert made.status_code == 200 and made.json()["view"] == view
    assert call(client, auth, "session_view.update", body, "collapse").json() == made.json()
    assert call(client, auth, "session_view.update", body, "different").status_code == 409
    assert call(client, auth, "session_view.update", {**body, "view": {**view, "structureCollapsed": []}}, "collapse").status_code == 409
    for groups in (["nodes", "nodes"], ["node-id"], [True], "areas", None):
        assert call(client, auth, "session_view.update", {"expectedRevision": 1,
            "view": {**view, "structureCollapsed": groups}}, "invalid").status_code == 422
    assert call(client, auth, "session_view.update", body, "foreign", scope={**SCOPE, "workspace": "main"}).status_code == 403
    _, token = tokens.issue_heart(service, "draft", "draft")
    assert "structureCollapsed" not in call(client, {**auth, tokens.HEADER: token}, "session_view.read").json()["view"]
    legacy = {key: value for key, value in view.items() if key != "structureCollapsed"}
    restored = call(client, auth, "session_view.update", {"expectedRevision": 1, "view": legacy}, "legacy")
    assert restored.status_code == 200 and restored.json()["view"] == legacy


def test_expiry_replacement_revocation_and_human_boundary(setup, monkeypatch):
    client, service, auth = setup
    session = call(client, auth, "session_view.read").json()["sessionId"]
    handle = post(client, "attach", {"sessionId": session}).json()
    assert client.post(BASE + "/poll", headers=auth, json={**SCOPE, **{k: handle[k] for k in ("sessionId", "attachmentId", "secret")}}).status_code == 403
    clock = view_attachments.time.time()
    monkeypatch.setattr(view_attachments.time, "time", lambda: clock + 61)
    assert post(client, "poll", handle).status_code == 409
    replacement = post(client, "attach", {"sessionId": session}).json()
    assert replacement["attachmentId"] != handle["attachmentId"]
    assert post(client, "ack", handle, revision=0, view={"selection": [], "viewport": None, "filter": ""}).status_code == 409
    tokens.revoke(service, "draft", session)
    assert post(client, "poll", replacement).status_code == 409
    expired, _ = tokens.issue_heart(service, "draft", "draft")
    with service.db_for("draft"):
        service.db_for("draft").execute("UPDATE gate_sessions SET expires_at='2000-01-01T00:00:00Z' WHERE id=?", (expired,))
    assert post(client, "attach", {"sessionId": expired}).status_code == 409
    listed = client.get(BASE + "/sessions", params=SCOPE).json()["sessions"]
    assert expired not in {row["sessionId"] for row in listed}
    client.cookies.clear()
    assert client.get(BASE + "/sessions", params=SCOPE, headers={"X-Opora-Actor": "human"}).status_code == 403
