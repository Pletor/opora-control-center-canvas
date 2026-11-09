"""Temporary AMPLE pilot: typed structure, context federation, source pins and two solutions."""
from fastapi.testclient import TestClient
from backend.app.factory import create_app
from backend.editor.node.test_removals import ORIGIN, HEADERS, node
from backend.api.editor.test_research_routes import card


def test_ample_context_and_two_project_solution_pilot(tmp_path):
    with TestClient(create_app(tmp_path / "data"),base_url=ORIGIN) as client:
        service=client.app.state.service
        ample=service.project_hub.empty_project({"name":"AMPLE","confirmed":True})["id"]
        other=service.project_hub.empty_project({"name":"Different app","confirmed":True})["id"]
        scope={"project":ample,"workspace":"draft"}
        typed=lambda key,parent,kind: {**node(key,parent),"element":{"kind":kind}}
        graph={"nodes":[node("ui",kind="sector"),node("backend",kind="sector"),node("database",kind="sector"),
                        typed("login","ui","form"),typed("isolation","backend","permission"),
                        typed("identity","backend","service"),typed("tenant","database","entity")],
               "edges":[{"id":"login_identity","source":"login","target":"identity","relation":"uses"},
                        {"id":"identity_tenant","source":"identity","target":"tenant","relation":"uses"}]}
        view=service.view(ample,"draft")
        service.save_graph(ample,"draft",graph,view["digest"])
        alternate={"nodes":[{**typed("login",None,"form"),"purpose":"Passwordless login without organizations"}],"edges":[]}
        service.save_graph(other,"draft",alternate,service.view(other,"draft")["digest"])
        def save(operations,key):
            response=client.post("/api/research",headers=HEADERS,json={**scope,"key":key,"operations":operations})
            assert response.status_code==200,response.text
            return response.json()
        login=card("login_design",kind="option",title="Login",summary="Tenant-aware session design")
        login["refs"]["nodeIds"]=["login"]
        isolation=card("tenant_rule",title="Tenant boundary",summary="Organization identity is mandatory")
        isolation["refs"]["nodeIds"]=["isolation"]
        source=card("common_source",title="Shared source",content="Original specification",verification={"status":"verified","method":"Specification checked","at":"2026-11-09"},sources=[{"ref":"https://example.org/session","platform":"web","quote":"Session has tenant identity","title":"Specification","accessedAt":"2026-11-09"}])
        save([login,isolation,source],"seed")
        pin={"projectId":ample,"workspaceId":"draft","id":"common_source","revision":1}
        for target in ("login","isolation"):
            response=client.post("/api/research/bindings",headers=HEADERS,json={**scope,"scopeNodeId":target,"source":pin,"expectedRevision":0,"archived":False})
            assert response.status_code==200,response.text
        def context(target):
            response=client.get("/api/research/context",params={**scope,"scopeNodeId":target})
            assert response.status_code==200,response.text
            return response.json()["records"]
        login_records=context("login"); isolation_records=context("isolation")
        assert not any(r["card"]["id"]=="tenant_rule" for r in login_records)
        assert not any(r["card"]["id"]=="login_design" for r in isolation_records)
        assert next(r for r in login_records if r["card"]["id"]=="common_source")["canonicalRef"]==pin
        assert next(r for r in isolation_records if r["card"]["id"]=="common_source")["canonicalRef"]==pin
        assert service.db_for(ample).execute("SELECT count(*) FROM research_card_revisions WHERE id='common_source'").fetchone()[0]==1
        save([{**source,"expectedRevision":1,"content":"New organizational model"}],"revision2")
        pinned=client.get("/api/research/cards/common_source",params={**scope,"revision":1}).json()["card"]
        assert pinned["content"]=="Original specification"
        assert any(r["canonicalRef"]==pin for r in context("login"))
        response=client.post("/api/research/knowledge-search",headers=HEADERS,json={**scope,"query":"login","resultType":"solution","scopes":[scope,{"project":other,"workspace":"draft"}]})
        assert response.status_code==200,response.text
        solutions=response.json()["solutions"]
        assert len(solutions)==2
        assert {s["solutionRef"]["projectId"] for s in solutions}=={ample,other}
        assert all(s["solutionRef"]["nodeId"]=="login" for s in solutions)
        assert all(s["verification"]["status"]=="unknown" for s in solutions)
        renamed=service.view(ample,"draft")["graph"]
        renamed={**renamed,"nodes":[{**n,"name":"Login renamed"} if n["id"]=="login" else n for n in renamed["nodes"]]}
        service.save_graph(ample,"draft",renamed,service.view(ample,"draft")["digest"])
        assert any(r["canonicalRef"]==pin for r in context("login"))
