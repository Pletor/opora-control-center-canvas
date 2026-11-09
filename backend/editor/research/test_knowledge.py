"""Federated source identity, immutable pins and project-token isolation through HTTP."""
import json
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, post
from backend.editor.node.test_removals import HEADERS, SCOPE, node, install_graph
from backend.brain_opora.determinism import tokens, brain_files
from backend.editor.research import service as research


def bind(client, source, target="s1", revision=0, archived=False, headers=HEADERS):
    return client.post("/api/research/bindings", headers=headers, json={**SCOPE, "scopeNodeId": target, "source": source, "expectedRevision": revision, "archived": archived})


def context(client, target="s1", headers=HEADERS):
    return client.get("/api/research/context", params={**SCOPE, "scopeNodeId": target}, headers=headers)


def search(client, scopes, headers=HEADERS, **extra):
    return client.post("/api/research/knowledge-search", headers=headers, json={**SCOPE, "scopes": scopes, "query": "Login", **extra})


def test_two_projects_distinct_solutions_one_shared_source_and_pinned_history(tmp_path):
    with client_with_sector(tmp_path) as client:
        service = client.app.state.service
        other = service.project_hub.empty_project({"name": "Other login", "confirmed": True})["id"]
        source = card("source", title="Shared verified source", verification={"status":"verified", "method":"Read specification", "at":"2026-11-09"}, sources=[{"ref":"https://example.org/session", "platform":"web", "quote":"Tenant boundary", "title":"Session", "accessedAt":"2026-11-09"}])
        assert post(client, [source, card("login", kind="option", summary="Login with tenant identity")]).status_code == 200
        research.apply(service, {"project":other,"workspace":"draft","key":"seed","operations":[card("login", kind="option", summary="Login without tenancy")]}, "human")
        install_graph(client, {"nodes": [node("s1",kind="sector"),node("s2",kind="sector")],"edges":[]})
        ref = {"projectId":"draft","workspaceId":"draft","id":"source","revision":1}
        assert bind(client,ref).status_code == 200
        assert bind(client,ref,target="s2").status_code == 200
        assert bind(client,ref).status_code == 409
        a = context(client).json()["records"]
        b = context(client,"s2").json()["records"]
        assert next(r for r in a if r["card"]["id"]=="source")["canonicalRef"] == next(r for r in b if r["card"]["id"]=="source")["canonicalRef"]
        assert service.db_for("draft").execute("SELECT count(*) FROM research_card_revisions WHERE id='source'").fetchone()[0] == 1
        changed = {**source,"expectedRevision":1,"content":"Changed source"}
        assert post(client,[changed],key="update").status_code==200
        pinned = [r for r in context(client).json()["records"] if r["card"]["id"]=="source" and any(c["relation"]=="shared" for c in r["contexts"])][0]
        assert pinned["canonicalRef"]["revision"] == 1
        results = search(client,[SCOPE,{"project":other,"workspace":"draft"}], kinds=["option"]).json()["results"]
        assert len(results)==2
        assert len({r["canonicalRef"]["projectId"] for r in results})==2
        assert len({r["card"]["summary"] for r in results})==2
        external={"projectId":other,"workspaceId":"draft","id":"login","revision":1}
        assert bind(client,external).status_code==200
        assert any(r["canonicalRef"]==external for r in context(client).json()["records"])


def test_scoped_agent_cannot_read_search_or_bind_foreign_source_even_with_ui_cookie(tmp_path):
    with client_with_sector(tmp_path) as client:
        service=client.app.state.service
        other=service.project_hub.empty_project({"name":"Secret project","confirmed":True})["id"]
        research.apply(service,{"project":other,"workspace":"draft","key":"seed","operations":[card()]},"human")
        external={"projectId":other,"workspaceId":"draft","id":"rc_login","revision":1}
        assert bind(client,external).status_code==200
        worker=tokens.issue_worker(service,"draft","draft",{"name":"reader"})
        auth={**HEADERS,tokens.HEADER:worker["token"]}
        assert context(client,headers=auth).status_code==200
        assert context(client,headers=auth).json()["records"]==[]
        assert search(client,[SCOPE,{"project":other,"workspace":"draft"}],headers=auth).status_code==403
        assert bind(client,external,headers=auth).status_code==403
        invalid={**HEADERS,tokens.HEADER:"revoked"}
        assert context(client,headers=invalid).status_code==401
        assert search(client,[SCOPE],headers=invalid).status_code==401


def test_parent_label_main_alias_pin_and_binding_archive(tmp_path):
    with client_with_sector(tmp_path) as client:
        service=client.app.state.service
        install_graph(client,{"nodes":[node("s1",kind="sector"),node("child",parent="s1")],"edges":[]})
        parent=card();parent["refs"]["nodeIds"]=["s1"]
        assert post(client,[parent]).status_code==200
        child=context(client,"child").json()["records"]
        assert child[0]["contexts"]==[{"relation":"parent","scopeNodeId":"s1"}]
        brain=brain_files.brain_dir(service,"draft");brain.mkdir(parents=True,exist_ok=True)
        (brain/brain_files.ACTIVE).write_text(json.dumps({"workspace":"draft"}))
        ref={"projectId":"draft","workspaceId":"main","id":"rc_login","revision":1}
        made=bind(client,ref,target="child")
        assert made.status_code==200,made.text
        assert made.json()["source"]["workspaceId"]=="draft"
        (brain/brain_files.ACTIVE).write_text(json.dumps({"workspace":"main"}))
        records=context(client,"child").json()["records"]
        assert len(records)==1 and {c["relation"] for c in records[0]["contexts"]}=={"parent","shared"}
        assert bind(client,made.json()["source"],target="child",revision=1,archived=True).status_code==200
        assert all(c["relation"]!="shared" for r in context(client,"child").json()["records"] for c in r["contexts"])
        assert bind(client,{**made.json()["source"],"revision":999},target="child").status_code==404


def test_solution_grouping_uses_stable_scope_not_document_count(tmp_path):
    with client_with_sector(tmp_path) as client:
        service=client.app.state.service
        other=service.project_hub.empty_project({"name":"Other", "confirmed":True})["id"]
        install_graph(client,{"nodes":[node("s1",kind="sector"),node("login"),node("isolation")],"edges":[]})
        view=service.view(other,"draft")
        service.save_graph(other,"draft",{"nodes":[node("login")],"edges":[]},view["digest"])
        for index in range(3):
            finding=card("fact"+str(index),title="Login fact")
            finding["refs"]["nodeIds"]=["login"]
            assert post(client,[finding],key="fact"+str(index)).status_code==200
        source=card("shared",title="Specification")
        assert post(client,[source],key="shared").status_code==200
        ref={"projectId":"draft","workspaceId":"draft","id":"shared","revision":1}
        assert bind(client,ref,target="login").status_code==200
        assert bind(client,ref,target="isolation").status_code==200
        result=search(client,[SCOPE,{"project":other,"workspace":"draft"}],resultType="solution")
        assert result.status_code==200,result.text
        solutions=result.json()["solutions"]
        assert len(solutions)==2
        assert {s["solutionRef"]["projectId"] for s in solutions}=={"draft",other}
        local=next(s for s in solutions if s["solutionRef"]["projectId"]=="draft")
        assert len([r for r in local["evidence"] if r["card"]["id"].startswith("fact")])==3
        assert any(r["card"]["id"]=="shared" for r in local["evidence"])
        assert local["verification"]["status"]=="unknown"
        assert search(client,[{**SCOPE,"scopeNodeId":"isolation","includeDescendants":False}],resultType="solution").json()["solutions"]==[]


def test_binding_cas_is_atomic_across_service_instances(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from backend.canvas.canvas_service import CanvasService
    from backend.editor.research import knowledge
    from backend.brain_opora.determinism.gate_payloads import GateError
    root=tmp_path/"shared"
    one=CanvasService(root); two=CanvasService(root)
    try:
        graph={"nodes":[node("s1",kind="sector")],"edges":[]}
        one.save_graph("draft","draft",graph,one.view("draft","draft")["digest"])
        research.apply(one,{**SCOPE,"key":"seed","operations":[card()]},"human")
        source={"projectId":"draft","workspaceId":"draft","id":"rc_login","revision":1}
        barrier=Barrier(2)
        def attempt(service):
            barrier.wait()
            try:
                knowledge.bind(service,"draft","draft","s1",source,0,False,lambda *args:None,"test")
                return 200
            except GateError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,(one,two)))
        assert sorted(results)==[200,409]
    finally:
        one.close();two.close()


def test_cross_workspace_pin_and_archived_project_are_not_copies_or_leaks(tmp_path):
    with client_with_sector(tmp_path) as client:
        service=client.app.state.service
        assert post(client,[card()]).status_code==200
        ref={"projectId":"draft","workspaceId":"draft","id":"rc_login","revision":1}
        from backend.canvas.test_workspace_graph import repository, workspace
        fixture_root=tmp_path/"gitfixture";fixture_root.mkdir()
        project,wid,_=workspace(service,repository(fixture_root,service.root))
        made=client.post("/api/research/bindings",headers=HEADERS,json={"project":project,"workspace":wid,"scopeNodeId":"","source":ref,"expectedRevision":0,"archived":False})
        assert made.status_code==200,made.text
        records=client.get("/api/research/context",params={"project":project,"workspace":wid}).json()["records"]
        assert records[0]["canonicalRef"]==ref
        assert service.db_for("draft").execute("SELECT count(*) FROM research_card_revisions").fetchone()[0]==1
        other=service.project_hub.empty_project({"name":"Will disconnect","confirmed":True})["id"]
        research.apply(service,{"project":other,"workspace":"draft","key":"seed","operations":[card()]},"human")
        source={**ref,"projectId":other}
        assert bind(client,source).status_code==200
        with service.registry_lock,service.db:
            service.db.execute("INSERT INTO archived_projects VALUES(?,?,?)",(other,"{}","2026-11-09"))
        assert not any(r["canonicalRef"]["projectId"]==other for r in context(client).json()["records"])
        assert search(client,[{"project":other,"workspace":"draft"}]).status_code==404
