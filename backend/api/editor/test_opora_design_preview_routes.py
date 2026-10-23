"""Cesty design náhledu: identita, zápis běhu, ETag/304, PNG soubor, potvrzení a režim jen pro člověka, strop těla."""
import json

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.editor.opora_design_preview_routes import create_design_preview_router
from backend.app.factory import create_app
from backend.canvas.test_opora_design_preview_validation import PNG, preview
from backend.canvas.test_opora_execution_pull_requests import SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import config, use
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

POST, GET = "/api/oporahub/review-jobs/preview", "/api/oporahub/review-preview"
CONFIRM, MODE = "/api/oporahub/review-preview/confirm", "/api/oporahub/design-mode"
AGENT, HUMAN = {"x-actor": "agent", "x-agent": "worker"}, {"x-actor": "human"}


def client_for(review):  # noqa: F811
    use(review, config())
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        actor = request.headers.get("x-actor", "")
        request.state.actor, request.state.agent = (actor or None), request.headers.get("x-agent")
        return await call_next(request)

    app.include_router(create_design_preview_router(review["service"], review["jobs"]))
    return TestClient(app)


def body(review, **changes):  # noqa: F811
    record = review["record"]
    return {**review["scope"], "executionId": record["executionId"], "token": record["token"], "epoch": record["epoch"],
            "preview": preview(**changes)}


def test_preview_route_contract_with_etag(review):  # noqa: F811
    client = client_for(review)
    query = {**review["scope"], "nodeId": "card"}
    assert client.post(POST, json=body(review)).status_code == 428
    assert client.get(GET, params=query).status_code == 428
    empty = client.get(GET, headers=AGENT, params=query)
    assert empty.status_code == 200 and empty.json()["heads"] == [] and empty.json()["design"]["mode"] == "brand"
    assert empty.json()["sketchUrl"] == "/api/layout-preview?project={project}&workspace={workspace}&layer=card".format(
        **review["scope"])
    assert empty.json()["designSystem"]["available"] is False  # test project has no source repository
    tokenless = {key: value for key, value in body(review).items() if key not in ("token", "epoch")}
    assert client.post(POST, headers=AGENT, json=tokenless).status_code == 409
    wrong = client.post(POST, headers=AGENT, json=body(review, headSha="d" * 40))
    assert wrong.status_code == 409 and wrong.json()["code"] == "review_conflict"
    done = client.post(POST, headers=AGENT, json=body(review))
    assert done.status_code == 200 and done.json()["recorded"] is True
    read = client.get(GET, headers=AGENT, params=query)
    head = read.json()["heads"][0]
    assert (head["headSha"], head["current"], head["by"], head["confirmed"]) == (SHA, True, "agent:worker", None)
    tag = read.headers["etag"]
    assert tag != empty.headers["etag"]
    cached = client.get(GET, headers={**AGENT, "if-none-match": tag}, params=query)
    assert cached.status_code == 304 and cached.content == b""
    picture = client.get(head["screenshots"][0]["url"], headers=AGENT)
    assert picture.status_code == 200 and picture.content == PNG and picture.headers["content-type"] == "image/png"
    assert "sandbox" in picture.headers["content-security-policy"]
    assert client.get(head["screenshots"][0]["url"], headers={**AGENT, "if-none-match": picture.headers["etag"]}
                      ).status_code == 304
    stranger = client.get("/api/oporahub/review-preview/file", headers=AGENT, params={**query, "fileId": "img"})
    assert stranger.status_code == 404  # only a screenshot of this card, never any drawing file
    assert client.get(GET, headers=AGENT, params={**query, "nodeId": "bad id!"}).status_code == 400


def test_confirm_and_mode_are_human_only(review):  # noqa: F811
    client = client_for(review)
    client.post(POST, headers=AGENT, json=body(review))
    confirm = {**review["scope"], "nodeId": "card", "headSha": SHA}
    agent = client.post(CONFIRM, headers=AGENT, json=confirm)
    assert agent.status_code == 403 and agent.json()["humanRequired"] is True
    assert client.post(CONFIRM, json=confirm).status_code == 428  # unknown origin, no UI session
    done = client.post(CONFIRM, headers=HUMAN, json=confirm)
    assert done.status_code == 200 and done.json()["confirmed"]["by"] == "human"
    query = {**review["scope"], "nodeId": "card"}
    assert client.get(GET, headers=HUMAN, params=query).json()["heads"][0]["confirmed"]["by"] == "human"
    assert client.post(CONFIRM, headers=HUMAN, json={**confirm, "headSha": "d" * 40}).status_code == 409
    mode = {**review["scope"], "nodeId": "card", "mode": "explore"}
    assert client.post(MODE, headers=AGENT, json=mode).status_code == 403
    assert client.post(MODE, json=mode).status_code == 428
    changed = client.post(MODE, headers=HUMAN, json=mode)
    assert changed.status_code == 200 and changed.json()["revision"] == 1
    assert client.get(GET, headers=AGENT, params=query).json()["design"]["mode"] == "explore"
    assert client.post(MODE, headers=HUMAN, json={**mode, "mode": "wild"}).status_code == 409


def test_bodies_are_capped_before_parsing(review):  # noqa: F811
    client = client_for(review)
    headers = {**AGENT, "content-type": "application/json"}
    huge = client.post(POST, headers={**headers, "content-length": str(24 * 1024 * 1024)}, content=b"{}")
    assert huge.status_code == 413 and huge.json()["code"] == "payload_too_large"
    assert client.post(POST, headers=headers, content=b"{not json").status_code == 400
    big = json.dumps({**review["scope"], "nodeId": "card", "headSha": SHA, "pad": "x" * 5000})
    assert client.post(CONFIRM, headers={**HUMAN, "content-type": "application/json"}, content=big).status_code == 413


def test_routes_are_registered_in_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    monkeypatch.setenv("OPORA_EXECUTION_PR_WORKER", "0")
    monkeypatch.setenv("OPORA_REVIEW_JOBS", "0")
    origin = "http://127.0.0.1:8740"
    with TestClient(create_app(tmp_path / "data"), base_url=origin) as client:
        agent = {"origin": origin, "X-Opora-Actor": "agent; name=worker"}
        response = client.post(POST, headers=agent, json={"project": "p", "workspace": "w"})
        assert response.status_code == 409 and response.json()["code"] == "review_conflict"
        large = client.post(POST, headers=agent, json={"project": "p", "workspace": "w", "pad": "x" * 3_000_000})
        assert large.status_code == 409  # above the app's 2 MB default: screenshots have their own cap
        confirm = client.post(CONFIRM, headers=agent, json={"project": "p", "workspace": "w"})
        assert confirm.status_code == 403  # the app's agent header never passes as a human
        mode = client.post(MODE, headers=agent, json={"project": "p", "workspace": "w"})
        assert mode.status_code == 403
        system = client.get("/api/oporahub/design-system", headers=agent, params={"project": "p"})
        assert system.status_code == 200 and system.json()["available"] is False
