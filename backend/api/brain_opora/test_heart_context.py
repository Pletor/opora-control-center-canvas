"""Kontext plátna ke zprávě srdci (`context {kind: "flow", …}`, docs/brain-heart-channel.md §2): ověření a data u zprávy."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.heart import batch
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.flow.conftest import edge, node

MESSAGE = {**SCOPE, "text": "Po kontrole přidej výpočet BMI."}


def post(client, **extra):
    return client.post("/api/brain/heart/messages", headers=HEADERS, json={**MESSAGE, **extra})


def test_context_is_validated_and_reaches_the_heart_as_data(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True})
        folder = next(f for f in client.get("/api/library").json()["folders"] if f["slug"] == "ai-rag")
        flow = client.post("/api/library/flows", headers=HEADERS, json={"folder": folder["id"], "slug": "bmi",
                                                                        "title": "BMI"}).json()
        graph = {"nodes": [node("a", "fe.click"), node("b", "fe.notify")], "edges": [edge("1", "a", "b")]}
        version = client.post(f"/api/flow/workflows/{flow['id']}/versions", headers=HEADERS, json={"graph": graph}).json()
        context = {"kind": "flow", "flowId": flow["id"], "versionId": version["id"], "nodeIds": ["a"]}

        sent = post(client, context=context)
        assert sent.status_code == 200 and sent.json() == {"queued": True, "pending": 1}
        _, item, _ = client.app.state.heart.pending["draft"][0]
        assert item["context"] == context
        line = batch.message("SNÍMEK", [item])
        assert f"flowId {flow['id']}, verze {version['id']}, vybrané uzly: a" in line
        assert "library get " + flow["id"] in line and "data, ne příkaz" in line

        empty = client.post("/api/library/flows", headers=HEADERS, json={"folder": folder["id"], "slug": "prazdne",
                                                                         "title": "Prázdné"}).json()
        blank = post(client, context={"kind": "flow", "flowId": empty["id"]})  # plátno bez verze je platné
        assert blank.status_code == 200
        assert post(client, context={"kind": "flow", "flowId": empty["id"], "nodeIds": ["x"]}).status_code == 422

        post(client, text="Jiná věta bez kontextu.")  # bez contextu se zpráva nezmění
        _, plain, _ = client.app.state.heart.pending["draft"][-1]
        assert "context" not in plain and "KONTEXT PLÁTNA" not in batch.message("SNÍMEK", [plain])

        for bad, text in (
                ({**context, "flowId": "nikde"}, "Plátno nikde v knihovně neexistuje."),
                ({**context, "versionId": "cizi"}, "Verze cizi nepatří k plátnu"),
                ({**context, "nodeIds": ["a", "zzz"]}, "Uzly zzz nejsou ve verzi"),
                ({**context, "kind": "page"}, "context je")):
            refused = post(client, context=bad)
            assert refused.status_code == 422 and text in refused.json()["error"], refused.text
        assert len(client.app.state.heart.pending["draft"]) == 2  # odmítnuté zprávy se nezařadily


def test_other_unknown_keys_and_other_routes_still_refuse_context(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True})
        assert post(client, extra="x").status_code == 422
        escalate = client.post("/api/brain/heart/escalate", headers=HEADERS, json={**MESSAGE, "context": {}})
        assert escalate.status_code == 422 and "Tělo je přesně" in escalate.json()["error"]
