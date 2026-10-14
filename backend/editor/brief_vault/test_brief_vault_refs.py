"""Odkazy do schránky: `fragmentRef` v canvas-plan (nové karty i extend), `fragmentRefs` ve stavu,
`ideas[].fragmentId`, sekce `fragments` v node-brief a schránka v uložené verzi plátna."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.brief_vault.brief_vault_refs import validate_refs
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE, install_graph, node

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=work-b1"}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("c1", "s1")], "edges": []})
        yield client


def vault(client, **body):
    response = client.post("/api/brief-vault", headers=AGENT, json={**SCOPE, **body})
    assert response.status_code == 200, response.text
    return response.json()


def plan(client, body, dry=False):
    digest = client.get("/api/view", params=SCOPE).json()["digest"]
    return client.post("/api/canvas-plan", headers=AGENT, json={**SCOPE, "digest": digest, "dryRun": dry, "plan": body})


def state(client):
    return client.get("/api/desktop-v3/state", params=SCOPE).json()


def fragment(client, text="3.37 Version activation"):
    return vault(client, op="create", scopeNodeId="s1", track="ux", title="3.37", text=text)["fragment"]


def test_state_refs_shape():
    validate_refs([{"fragmentId": "a", "revision": 1}])
    for broken in ([{"fragmentId": "a"}], [{"fragmentId": "a", "revision": 0}], [{"fragmentId": "../x", "revision": 1}],
                   [{"fragmentId": "a", "revision": 1}] * 2, [{"fragmentId": str(n), "revision": 1} for n in range(51)]):
        with pytest.raises(ValueError):
            validate_refs(broken)


def test_plan_fragment_ref_missing_is_409_and_valid_lands_in_state(client):
    missing = plan(client, {"nodes": [{"ref": "k", "kind": "node", "parent": "@s1", "name": "[task] K",
                                       "fragmentRef": {"fragmentId": "neexistuje"}}]})
    assert missing.status_code == 409 and "neexistuje" in missing.json()["error"]
    item = fragment(client)
    too_new = plan(client, {"nodes": [{"ref": "k", "kind": "node", "parent": "@s1", "name": "[task] K",
                                       "fragmentRef": {"fragmentId": item["id"], "revision": 2}}]})
    assert too_new.status_code == 409
    ok = plan(client, {"nodes": [{"ref": "k", "kind": "node", "parent": "@s1", "name": "[task] K",
                                  "fragmentRef": {"fragmentId": item["id"]}}]})
    assert ok.status_code == 200, ok.text
    card = ok.json()["refs"]["k"]
    assert state(client)["state"]["nodes"][card]["fragmentRefs"] == [{"fragmentId": item["id"], "revision": 1}]
    tree = client.get("/api/brief-vault", params=SCOPE).json()["roots"][0]
    assert tree["inserted"] is True and tree["cards"] == [{"nodeId": card, "revision": 1}]


def test_extend_adds_refs_to_existing_card_and_deleted_fragment_is_rejected(client):
    first, second = fragment(client), fragment(client, "3.42 Retrieval")
    revision = state(client)["revision"]
    ok = plan(client, {"extend": [{"node": "@c1", "expectedRevision": revision,
                                   "fragmentRef": [{"fragmentId": first["id"]}, {"fragmentId": second["id"], "revision": 1}]}]})
    assert ok.status_code == 200, ok.text
    assert [ref["fragmentId"] for ref in state(client)["state"]["nodes"]["c1"]["fragmentRefs"]] == [first["id"], second["id"]]
    third = fragment(client, "smazat")
    client.post("/api/brief-vault", headers=HEADERS, json={**SCOPE, "op": "delete", "fragmentId": third["id"],
                                                          "expectedRevision": 1, "note": "pryč"})
    rejected = plan(client, {"extend": [{"node": "@c1", "expectedRevision": state(client)["revision"],
                                         "fragmentRef": {"fragmentId": third["id"]}}]})
    assert rejected.status_code == 409


def test_node_brief_has_verbatim_text_and_changed_since_insert(client):
    item = fragment(client, "Doslovné zadání\n\ns mezerami  ")
    plan(client, {"extend": [{"node": "@c1", "expectedRevision": state(client)["revision"],
                              "fragmentRef": {"fragmentId": item["id"]}}]})
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()["fragments"]
    assert brief["items"][0]["text"] == "Doslovné zadání\n\ns mezerami  " and brief["items"][0]["changedSinceInsert"] is False
    vault(client, op="revise", fragmentId=item["id"], expectedRevision=1, text="v2", note="změna")
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()["fragments"]
    assert brief["items"][0] | {"text": "v2", "insertedRevision": 1, "revision": 2, "changedSinceInsert": True} == brief["items"][0]
    assert brief["changed"] == 1 and brief["items"][0]["path"] == ["3.37"]
    assert client.get("/api/brief-vault", params=SCOPE).json()["roots"][0]["status"] == "changed"


def test_state_save_checks_new_refs_and_idea_fragment_ids(client):
    item = fragment(client)
    current = state(client)
    good = {"phase": "discover", "criteria": [], "steps": [], "fragmentRefs": [{"fragmentId": item["id"], "revision": 1}],
            "ideas": [{"id": "i1", "text": "Doplnit test.", "by": "human", "source": "human", "at": "T", "status": "open",
                       "fragmentId": item["id"]}]}
    for broken in ({**good, "fragmentRefs": [{"fragmentId": "cizi", "revision": 1}]},
                   {**good, "ideas": [{**good["ideas"][0], "fragmentId": "cizi"}]}):
        response = client.post("/api/desktop-v3/state", headers=HEADERS, json={
            **SCOPE, "expectedRevision": current["revision"], "state": {**current["state"], "nodes": {"c1": broken}}})
        assert response.status_code == 409, response.text
    response = client.post("/api/desktop-v3/state", headers=HEADERS, json={
        **SCOPE, "expectedRevision": current["revision"], "state": {**current["state"], "nodes": {"c1": good}}})
    assert response.status_code == 200, response.text
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": item["id"]}).json()
    assert detail["ideas"][0]["ideaId"] == "i1" and detail["cards"][0]["nodeId"] == "c1"


def test_canvas_version_saves_and_restores_brief_vault(client):
    from backend.editor.canvas_versions.test_canvas_versions import digest, save, versions
    item = fragment(client, "verze 1")
    saved = save(client).json()["version"]
    vault(client, op="revise", fragmentId=item["id"], expectedRevision=1, text="verze 2", note="změna")
    later = fragment(client, "vznikl po verzi")
    restored = client.post("/api/canvas-versions/restore", headers=HEADERS, json={
        **SCOPE, "versionId": saved["id"], "digest": digest(client), "author": "test",
        "expectedToken": versions(client)["currentToken"]})
    assert restored.status_code == 200, restored.text
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": item["id"]}).json()
    assert detail["fragment"]["text"] == "verze 1" and detail["latestRevision"] == 3
    assert [root["id"] for root in client.get("/api/brief-vault", params=SCOPE).json()["roots"]] == [item["id"]]
    # Fragment vzniklý po verzi je skrytý, jeho doslovný text zůstal v historii.
    history = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": later["id"], "revision": 1}).json()
    assert history["fragment"]["text"] == "vznikl po verzi" and history["history"][-1]["deleted"] is True
    assert versions(client)["dirty"] is False
