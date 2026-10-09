"""`/api/brief-vault`: čtení stromu a fragmentu, zápis op, guardy člověka (agent 403, neznámý 428)."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE, install_graph, node

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=work-b1"}


def client_with_sector(tmp_path):
    client = TestClient(create_app(tmp_path), base_url=ORIGIN)
    install_graph(client, {"nodes": [node("s1", kind="sector")], "edges": []})
    return client


def post(client, headers=AGENT, **body):
    return client.post("/api/brief-vault", headers=headers, json={**SCOPE, **body})


def test_agent_creates_splits_and_reads_tree_and_fragment(tmp_path):
    with client_with_sector(tmp_path) as client:
        created = post(client, op="create", scopeNodeId="s1", title="Vrstva", text="A\n\n3.1 B")
        assert created.status_code == 200, created.text
        fragment = created.json()["fragment"]
        assert fragment["by"] == "work-b1" and fragment["actor"] == "agent"
        split = post(client, op="split", fragmentId=fragment["id"], expectedRevision=1, splitter="heading-number")
        assert split.status_code == 200 and len(split.json()["children"]) == 2
        tree = client.get("/api/brief-vault", params={**SCOPE, "scope": "s1"}).json()
        assert tree["roots"][0]["coverage"]["leaves"] == 2 and "text" not in tree["roots"][0]
        assert client.get("/api/brief-vault", params={**SCOPE, "scope": "jiny"}).json()["roots"] == []
        detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": fragment["id"], "revision": 1}).json()
        assert detail["fragment"]["text"] == "A\n\n3.1 B" and detail["latestRevision"] == 1


def test_split_mismatch_and_stale_revision_are_409(tmp_path):
    with client_with_sector(tmp_path) as client:
        fragment = post(client, op="create", scopeNodeId="s1", title="V", text="A\n\nB").json()["fragment"]
        mismatch = post(client, op="split", fragmentId=fragment["id"], expectedRevision=1,
                        parts=[{"title": "a", "text": "A"}, {"title": "b", "text": "X"}])
        assert mismatch.status_code == 409 and "ztratilo" in mismatch.json()["error"]
        stale = post(client, op="revise", fragmentId=fragment["id"], expectedRevision=5, text="x", note="n")
        assert stale.status_code == 409
        assert post(client, op="nope").status_code == 409


def test_human_only_ops_403_for_agent_428_for_unknown_200_for_human(tmp_path):
    with client_with_sector(tmp_path) as client:
        fragment = post(client, op="create", scopeNodeId="s1", title="V", text="t").json()["fragment"]
        body = {"op": "set-mvp", "fragmentIds": [fragment["id"]], "mvp": "yes"}
        assert post(client, **body).status_code == 403
        cookies = dict(client.cookies)
        client.cookies.clear()
        assert post(client, headers=HEADERS, **body).status_code == 428
        for key, value in cookies.items():
            client.cookies.set(key, value)
        assert post(client, headers=HEADERS, **body).status_code == 200
        delete = {"op": "delete", "fragmentId": fragment["id"], "expectedRevision": 2, "note": "pryč"}
        assert post(client, **delete).status_code == 403
        assert post(client, headers=HEADERS, **delete).status_code == 200
        restore = {"op": "restore", "fragmentId": fragment["id"], "expectedRevision": 3, "revision": 2, "note": "zpět"}
        assert post(client, **restore).status_code == 403
        assert post(client, headers=HEADERS, **restore).json()["fragment"]["mvp"] == "yes"
