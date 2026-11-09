"""Hybrid precision, ACL-before-worker, canonical identity and truthful fallback."""
from copy import deepcopy
import math
import pytest
from backend.canvas.canvas_service import CanvasService
from backend.editor.research import knowledge, solution_ranking, solution_comparison
from backend.editor.node.test_removals import node
from backend.brain_opora.determinism.gate_payloads import GateError


def candidate(id="login", **extra):
    return {"project":"p","workspace":"w","node":{"id":id,"name":id},"text":"Own authentication description",
            "textTruncated":False,"semanticEligible":True,"lexical":0,"graph":0,**extra}


def test_hybrid_keeps_lexical_anchor_and_excludes_merely_related_context():
    ranked,meta=solution_ranking.rank([candidate(lexical=1),candidate("tenant",graph=1)],"login",runner=lambda *args:[.88,.84])
    assert [item["node"]["id"] for item in ranked]==["login"]
    assert meta["used"]=="hybrid" and ranked[0]["match"]["semantic"]==.88
    ranked,_=solution_ranking.rank([candidate(),candidate("shared_only",semanticEligible=False)],"paraphrase",runner=lambda *args:[.86,.99])
    assert [item["node"]["id"] for item in ranked]==["login"]


@pytest.mark.parametrize("scores",[[math.nan],[math.inf],[True],[],None,[1.5]])
def test_invalid_dense_result_is_a_truthful_exact_lexical_fallback(scores):
    ranked,meta=solution_ranking.rank([candidate(lexical=1)],"login",runner=lambda *args:scores)
    assert meta["used"]=="lexical" and meta["semantic"]["status"]=="unavailable"
    assert ranked[0]["match"]["semantic"] is None


def test_lexical_option_does_not_invoke_worker_and_preserves_all_terms():
    def fail(*args):raise AssertionError("worker must stay cold")
    result,meta=solution_ranking.rank([candidate(lexical=1),candidate("partial",lexical=.5)],"two words","lexical",fail)
    assert len(result)==1 and meta["semantic"]["status"]=="not_requested"
    result,_=solution_ranking.rank([candidate(lexical=1,legacyLexical=False)],"a login","lexical",fail)
    assert result==[]  # Stop-word normalization must not broaden legacy/fallback admission.


def test_all_projects_authorize_before_worker_or_foreign_read(tmp_path):
    canvas=CanvasService(tmp_path/"data")
    try:
        other=canvas.project_hub.empty_project({"name":"Secret","confirmed":True})["id"]
        calls=[]
        def authorize(project,*args):
            calls.append(project)
            if project==other:raise GateError(403,"gate_scope","denied","")
        def worker(*args):raise AssertionError("unauthorized text reached worker")
        with pytest.raises(GateError):
            knowledge.solutions(canvas,[{"project":"draft","workspace":"draft"},{"project":other,"workspace":"draft"}],"login",10,authorize,runner=worker)
        assert calls==["draft",other]
    finally:canvas.close()


def test_candidate_bound_is_disclosed_and_scope_does_not_leak_sibling(tmp_path):
    canvas=CanvasService(tmp_path/"data")
    try:
        graph={"nodes":[node("sector",kind="sector"),*[node(f"login{i}","sector") for i in range(130)],node("sibling")],"edges":[]}
        canvas.save_graph("draft","draft",graph,canvas.view("draft","draft")["digest"])
        seen=[]
        def worker(query,chunks):seen.extend(chunks);return [.9]*len(chunks)
        response=knowledge.solutions(canvas,[{"project":"draft","workspace":"draft","scopeNodeId":"sector"}],"login",100,lambda *args:None,runner=worker)
        assert len(seen)==128 and response["retrieval"]["candidates"]==131
        assert response["truncated"] and response["retrieval"]["truncated"]
        assert all(solution["solutionRef"]["nodeId"]!="sibling" for solution in response["solutions"])
    finally:canvas.close()


def test_comparison_uses_stored_values_and_exact_shared_revision():
    ref={"projectId":"origin","workspaceId":"work","id":"source","revision":3}
    first={"solutionRef":{"projectId":"a","nodeId":"login"},"snapshot":{"workspaceId":"w"},"purpose":"Password",
           "element":{"kind":"form"},"facts":{"inputs":[],"sources":[ref],"specification":{"fields":{"goal":"Tenant session"}}}}
    second=deepcopy(first);second["solutionRef"]["projectId"]="b";second["purpose"]="Email link"
    result=solution_comparison.compare([first,second])
    assert result["commonSources"]==[ref]
    assert result["differences"]==[{"field":"purpose","values":[{"solutionRef":first["solutionRef"],"workspaceId":"w","value":"Password"},{"solutionRef":second["solutionRef"],"workspaceId":"w","value":"Email link"}]}]
    second["facts"]["sources"][0]["revision"]=4
    assert solution_comparison.compare([first,second])["commonSources"]==[]


def test_factual_inputs_include_real_inherited_requirement_origin():
    graph={"nodes":[{**node("parent",kind="sector"),"name":"Parent"},node("child","parent"),node("input")],
           "edges":[{"id":"required","source":"parent","target":"input","relation":"requires",
                     "requirement":{"readiness":"design","revision":3}}]}
    result=solution_comparison.facts({"node":{"id":"child"},"view":{"graph":graph},"specification":None,"evidence":[]})
    assert result["inputs"]==[{"nodeId":"input","name":"input","sourceNodeId":"parent","sourceName":"Parent",
                               "relation":"requires","requirement":{"readiness":"design","revision":3}}]
