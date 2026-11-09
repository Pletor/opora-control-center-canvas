"""Existing endpoint defaults to hybrid, isolates sources and retains workspace variants."""
from fastapi.testclient import TestClient
from backend.app.factory import create_app
from backend.editor.node.test_removals import HEADERS, ORIGIN, node
from backend.editor.research import knowledge, solution_ranking
from backend.brain_opora.determinism import tokens


def test_existing_endpoint_uses_worker_by_default_and_foreign_acl_precedes_it(tmp_path,monkeypatch):
    calls=[]
    def worker(query,chunks):calls.append(chunks);return [.9]*len(chunks)
    monkeypatch.setattr(solution_ranking,"WorkerRunner",lambda:worker)
    with TestClient(create_app(tmp_path/"data"),base_url=ORIGIN) as client:
        canvas=client.app.state.service
        canvas.save_graph("draft","draft",{"nodes":[node("login")],"edges":[]},canvas.view("draft","draft")["digest"])
        body={"project":"draft","workspace":"draft","scopes":[{"project":"draft","workspace":"draft"}],"query":"login","resultType":"solution"}
        response=client.post("/api/research/knowledge-search",headers=HEADERS,json=body)
        assert response.status_code==200,response.text
        assert calls and response.json()["retrieval"]["used"]=="hybrid"
        calls.clear()
        lexical=client.post("/api/research/knowledge-search",headers=HEADERS,json={**body,"ranking":"lexical"})
        assert lexical.status_code==200 and not calls
        assert lexical.json()["ranking"]=="lexical-all-terms"
        other=canvas.project_hub.empty_project({"name":"Secret","confirmed":True})["id"]
        token=tokens.issue_worker(canvas,"draft","draft",{"name":"reader"})["token"]
        denied=client.post("/api/research/knowledge-search",headers={**HEADERS,tokens.HEADER:token},json={**body,"scopes":[*body["scopes"],{"project":other,"workspace":"draft"}]})
        assert denied.status_code==403 and not calls


def test_one_solution_retains_two_authorized_workspace_snapshots(tmp_path):
    from backend.canvas.test_workspace_graph import repository, workspace
    from backend.canvas.canvas_service import CanvasService
    canvas=CanvasService(tmp_path/"data")
    try:
        project,one,_=workspace(canvas,repository(tmp_path,canvas.root))
        two=canvas._add_worktree(project,"second","Agent")["id"]
        for wid,purpose in ((one,"Password sign in"),(two,"Passwordless sign in")):
            canvas.save_graph(project,wid,{"nodes":[{**node("login"),"purpose":purpose}],"edges":[]},canvas.view(project,wid)["digest"])
        response=knowledge.solutions(canvas,[{"project":project,"workspace":one},{"project":project,"workspace":two}],"login",10,lambda *args:None,runner=lambda q,c:[.9]*len(c))
        assert len(response["solutions"])==1
        solution=response["solutions"][0]
        assert solution["solutionRef"]=={"projectId":project,"nodeId":"login"}
        assert {snapshot["workspaceId"] for snapshot in solution["snapshots"]}=={one,two}
    finally:canvas.close()


def test_denied_shared_origin_is_not_in_passages_refs_or_counts(tmp_path):
    from backend.canvas.canvas_service import CanvasService
    from backend.editor.research import service as research
    from backend.api.editor.test_research_routes import card
    from backend.brain_opora.determinism.gate_payloads import GateError
    canvas=CanvasService(tmp_path/"data")
    try:
        foreign=canvas.project_hub.empty_project({"name":"Secret origin","confirmed":True})["id"]
        canvas.save_graph("draft","draft",{"nodes":[{**node("login"),"purpose":"A password verifies the user and starts a session."}],"edges":[]},canvas.view("draft","draft")["digest"])
        research.apply(canvas,{"project":foreign,"workspace":"draft","key":"secret","operations":[card("secret",title="PrivateSecret",summary="HiddenSourceDescription")]},"human")
        ref={"projectId":foreign,"workspaceId":"draft","id":"secret","revision":1}
        knowledge.bind(canvas,"draft","draft","login",ref,0,False,lambda *args:None,"test")
        def authorize(project,*args):
            if project==foreign:raise GateError(403,"gate_scope","denied","")
        passages=[]
        def worker(query,chunks):passages.extend(chunks);return [.9]*len(chunks)
        response=knowledge.solutions(canvas,[{"project":"draft","workspace":"draft"}],"login",10,authorize,runner=worker)
        assert "PrivateSecret" not in str(passages) and "HiddenSourceDescription" not in str(passages)
        assert response["solutions"][0]["facts"]["sources"]==[]
        assert response["solutions"][0]["evidence"]==[]
    finally:canvas.close()
