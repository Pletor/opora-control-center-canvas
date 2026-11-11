from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.flow.catalogs.test_data_flow import rag

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}


def test_library_api_parts_lineage_and_flow_engine(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as c:
        pid = c.post("/api/empty-project", headers=HEADERS, json={"name": "Web", "confirmed": True}).json()["id"]
        _, token = tokens.issue_heart(c.app.state.service, pid, "draft")
        heart = {**AGENT, tokens.HEADER: token}
        human = c.get("/api/library", params={"owner": "human"}).json()["folders"]
        rag_folder = next(f for f in human if f["slug"] == "ai-rag")
        assert human[0]["title"] == "Databáze" and rag_folder["flows"] == []
        assert c.get("/api/library", params={"owner": "nikdo"}).status_code == 422

        body = {"folder": rag_folder["id"], "slug": "rag", "title": "RAG – ingest a dotaz"}
        assert c.post("/api/library/flows", headers=heart, json=body).status_code == 403  # část člověka
        flow = c.post("/api/library/flows", headers=HEADERS, json=body).json()
        assert flow["ownerRef"] == "opora:library:human:ai-rag/rag"
        assert c.post("/api/library/flows", headers=HEADERS, json=body).json()["code"] == "owner_taken"
        legacy = c.post("/api/flow/workflows", headers=HEADERS, json={"kind": "library_flow", "name": "X"})
        assert legacy.status_code == 422

        versions = f"/api/flow/workflows/{flow['id']}/versions"
        assert c.post(versions, headers=AGENT, json={"graph": rag()}).status_code == 403  # bez tokenu srdce
        vid = c.post(versions, headers=HEADERS, json={"graph": rag()}).json()["id"]
        c.post(f"/api/flow/versions/{vid}/candidate", headers=HEADERS, json={})
        assert c.post(f"/api/flow/versions/{vid}/activate", headers=HEADERS, json={}).json()["status"] == "active"
        runs = c.post(f"/api/flow/versions/{vid}/runs", headers=HEADERS, json={})
        assert runs.status_code == 409 and runs.json()["code"] == "not_runnable"

        types = c.get("/api/flow/node-types", params={"kind": "library_flow"}).json()["node_types"]
        agent_type = next(t for t in types if t["type"] == "ai.agent")
        assert agent_type["category"] == "ai" and agent_type["dynamicPorts"] is True
        assert {"name": "model", "required": True, "cardinality": "one"}.items() <= next(
            p for p in agent_type["ports"] if p["name"] == "model").items()
        broken = {**rag(), "edges": [e for e in rag()["edges"] if e["kind"] != "model"], "groups": []}
        check = c.post("/api/flow/graph-check", headers=HEADERS, json={"kind": "library_flow", "graph": broken}).json()
        assert check == {"ok": False, "errors": ["Uzel agent: povinný port model není připojený."]}

        copy = c.post(f"/api/library/flows/{flow['id']}/adopt", headers=HEADERS,
                      json={"project": pid, "nodeId": "rag"}).json()
        assert copy["projectId"] == pid and copy["derivedFrom"] == {"workflowId": flow["id"], "versionId": vid}

        agent_folder = c.post("/api/library/folders", headers=AGENT,
                              json={"owner": "agent", "slug": "ai-rag", "title": "AI a RAG"})
        assert agent_folder.status_code == 401  # agent bez tokenu brány
        assert c.post("/api/library/folders", headers=heart, json={"owner": "human", "slug": "x", "title": "X"}
                      ).status_code == 403
        agent_folder = c.post("/api/library/folders", headers=heart,
                              json={"owner": "agent", "slug": "ai-rag", "title": "AI a RAG"}).json()
        better = c.post(f"/api/library/flows/{copy['id']}/contribute", headers=heart,
                        json={"folder": agent_folder["id"], "slug": "rag-v2", "title": "RAG v2"}).json()
        assert better["derivedFrom"]["workflowId"] == copy["id"]
        assert c.post(f"/api/flow/workflows/{better['id']}/versions", headers=heart,
                      json={"graph": rag()}).status_code == 200  # knihovna agenta: agent píše
        detail = c.get(f"/api/library/flows/{flow['id']}").json()
        assert detail["derivedCount"] == 1 and detail["projects"] == [pid]

        assert c.post(f"/api/library/flows/{better['id']}/promote", headers=heart, json={}).status_code == 403
        promoted = c.post(f"/api/library/flows/{better['id']}/promote", headers=HEADERS, json={}).json()
        assert promoted["ownerRef"] == "opora:library:human:ai-rag/rag-v2"
        patched = c.patch(f"/api/library/folders/{agent_folder['id']}", headers=heart, json={"title": "RAG"})
        assert patched.json()["title"] == "RAG"
        assert c.request("DELETE", f"/api/library/folders/{agent_folder['id']}", headers=heart, json={}).json() == {
            "deleted": agent_folder["id"]}
        assert c.request("DELETE", f"/api/library/folders/{rag_folder['id']}", headers=HEADERS, json={}).json()["code"] == \
            "folder_not_empty"


def test_heart_proposes_a_draft_to_the_human_library_and_only_the_human_decides(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as c:
        pid = c.post("/api/empty-project", headers=HEADERS, json={"name": "Web", "confirmed": True}).json()["id"]
        heart = {**AGENT, tokens.HEADER: tokens.issue_heart(c.app.state.service, pid, "draft")[1]}
        folder = next(f for f in c.get("/api/library").json()["folders"] if f["slug"] == "ai-rag")
        flow = c.post("/api/library/flows", headers=HEADERS, json={"folder": folder["id"], "slug": "rag", "title": "RAG"}
                      ).json()
        versions = f"/api/flow/workflows/{flow['id']}/versions"
        first = c.post(versions, headers=HEADERS, json={"graph": rag()}).json()
        assert first["meta"] is None
        draft = c.post(versions, headers=heart, json={"graph": rag(), "note": "Přidat reranker"}).json()
        assert draft["status"] == "draft" and draft["meta"] == {
            "note": "Přidat reranker", "proposedBy": {"role": "heart", "project": pid}}
        for step in ("candidate", "activate"):  # aktivovat v části člověka srdce nesmí
            assert c.post(f"/api/flow/versions/{draft['id']}/{step}", headers=heart, json={}).status_code == 403
        reject = f"/api/flow/versions/{draft['id']}/reject"
        assert c.post(reject, headers=heart, json={"reason": "ne"}).status_code == 403
        assert c.post(reject, headers=HEADERS, json={"reason": "Reranker zatím ne"}).json()["status"] == "retired"

        agent_folder = c.post("/api/library/folders", headers=heart,
                              json={"owner": "agent", "slug": "ai-rag", "title": "AI a RAG"}).json()
        mine = c.post("/api/library/flows", headers=heart,
                      json={"folder": agent_folder["id"], "slug": "rag", "title": "RAG"}).json()
        learned = {"project": pid, "card": "rag", "result": "verified"}
        vid = c.post(f"/api/flow/workflows/{mine['id']}/versions", headers=heart,
                     json={"graph": rag(), "learnedFrom": learned}).json()["id"]
        c.post(f"/api/flow/versions/{vid}/candidate", headers=heart, json={})
        c.post(f"/api/flow/versions/{vid}/activate", headers=heart, json={})
        listed = c.get("/api/library", params={"owner": "agent"}).json()["folders"][0]["flows"][0]
        assert listed["learnedFrom"] == learned and listed["activeN"] == 1


def test_brief_route_serves_active_or_given_version_and_refuses_empty_or_missing(tmp_path):
    from backend.flow.test_simulate import BAD_CASE, OK_CASE, bmi_graph

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as c:
        folder = next(f for f in c.get("/api/library").json()["folders"] if f["slug"] == "functions")
        flow = c.post("/api/library/flows", headers=HEADERS,
                      json={"folder": folder["id"], "slug": "ulozit-bmi", "title": "Uložit BMI"}).json()
        url, versions = f"/api/library/flows/{flow['id']}/brief", f"/api/flow/workflows/{flow['id']}/versions"
        assert c.get(url).status_code == 404 and c.get(url).json()["detail"] == "Plátno nemá aktivní verzi."
        empty = c.post(versions, headers=HEADERS, json={"graph": {"nodes": [], "edges": []}}).json()
        assert c.get(url, params={"version": empty["n"]}).status_code == 422
        assert c.get(url, params={"version": empty["n"]}).json()["detail"] == "Plátno nemá žádné kroky."
        for case in ([OK_CASE], [OK_CASE, BAD_CASE]):
            vid = c.post(versions, headers=HEADERS, json={"graph": bmi_graph(case)}).json()["id"]
            c.post(f"/api/flow/versions/{vid}/candidate", headers=HEADERS, json={})
            c.post(f"/api/flow/versions/{vid}/activate", headers=HEADERS, json={})
        active = c.get(url).json()
        assert "Neplatná výška (`bad`)" in active["markdown"] and active["markdown"].endswith("tiše.\n")
        assert "opora:library:human:functions/ulozit-bmi@3" in active["markdown"]
        first = c.get(url, params={"version": 2}).json()
        assert "Neplatná výška (`bad`)" not in first["markdown"] and "@2" in first["markdown"]
        assert c.get(url, params={"version": 9}).json()["detail"] == "Plátno nemá verzi 9."
        assert c.get("/api/library/flows/nope/brief").status_code == 404


def test_element_logic_flow_route_finds_creates_once_and_takes_versions(tmp_path):
    from backend.project.architecture.test_page_plan import graph

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as c:
        pid = c.post("/api/empty-project", headers=HEADERS, json={"name": "Kurz", "confirmed": True}).json()["id"]
        scope = {"project": pid, "workspace": "draft"}
        digest = c.get("/api/view", params=scope).json()["digest"]
        assert c.post("/api/graph", headers=HEADERS, json={**scope, "graph": graph(), "digest": digest}).status_code == 200
        url = "/api/library/project-flows"
        assert c.get(url, params={"project": pid, "nodeId": "koupit"}).json() == {"flow": None}
        assert c.post(url, headers=HEADERS, json={**scope, "nodeId": "nic", "title": "X"}).status_code == 404
        assert c.post(url, headers=HEADERS, json={**scope, "nodeId": "kurz", "title": "X"}).status_code == 422
        assert c.post(url, headers=HEADERS, json={**scope, "workspace": "jiny", "nodeId": "koupit", "title": "X"}
                      ).status_code == 422

        made = c.post(url, headers=HEADERS, json={"project": pid, "nodeId": "koupit", "title": "Koupit kurz"}).json()
        assert made["ownerRef"] == "opora:project-flow:koupit" and made["projectId"] == pid and made["versions"] == []
        again = c.post(url, headers=HEADERS, json={**scope, "nodeId": "koupit", "title": "Znovu"}).json()
        assert again["id"] == made["id"] and again["title"] == "Koupit kurz"
        assert c.get(url, params={"project": pid, "nodeId": "koupit"}).json()["flow"]["id"] == made["id"]

        versions = f"/api/flow/workflows/{made['id']}/versions"
        assert c.post(versions, headers=HEADERS, json={"graph": rag()}).status_code == 200
        heart = {**AGENT, tokens.HEADER: tokens.issue_heart(c.app.state.service, pid, "draft")[1]}
        assert c.post(versions, headers=heart, json={"graph": rag(), "note": "Logika srdce"}).status_code == 200

        folder = next(f for f in c.get("/api/library").json()["folders"] if f["slug"] == "payments")
        source = c.post("/api/library/flows", headers=HEADERS, json={"folder": folder["id"], "slug": "platba", "title": "Platba"}
                        ).json()
        c.post(f"/api/flow/workflows/{source['id']}/versions", headers=HEADERS, json={"graph": rag()})
        taken = c.post(f"/api/library/flows/{source['id']}/adopt", headers=HEADERS, json={"project": pid, "nodeId": "koupit"})
        assert taken.status_code == 409 and taken.json()["code"] == "owner_taken"  # prvek už plátno má
