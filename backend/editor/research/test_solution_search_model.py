"""One real installed local model acceptance: paraphrase, two solutions, unrelated negatives."""
import pytest
from backend.canvas.canvas_service import CanvasService
from backend.editor.research import knowledge, service as research
from backend.api.editor.test_research_routes import card
from backend.editor.node.test_removals import node
from backend.semantic_retrieval.service import SemanticRetrieval, WorkerRunner


def test_actual_local_model_finds_two_czech_paraphrases_without_shared_meaningful_words(tmp_path):
    if SemanticRetrieval(None).availability_detail() or not WorkerRunner().python.is_file():
        pytest.skip("Pinned local ONNX model or its system worker is not installed")
    canvas=CanvasService(tmp_path/"data")
    try:
        other=canvas.project_hub.empty_project({"name":"Druhá aplikace","confirmed":True})["id"]
        first={**node("login"),"name":"Přihlášení","purpose":"Autentizace uživatele heslem, ověření identity a bezpečné vytvoření relace.","element":{"kind":"form"}}
        second={**node("access"),"name":"Jednorázový odkaz","purpose":"Bezheslové přihlášení pomocí emailu do uživatelského účtu.","element":{"kind":"form"}}
        invoice={**node("invoice"),"name":"Export faktur","purpose":"Výpis účetních dokladů do tabulky CSV.","element":{"kind":"service"}}
        isolation={**node("isolation"),"name":"Izolace organizací","purpose":"Oddělení dat jednotlivých tenantů.","element":{"kind":"permission"}}
        for project,nodes in (("draft",[first,invoice,isolation]),(other,[second])):
            canvas.save_graph(project,"draft",{"nodes":nodes,"edges":[]},canvas.view(project,"draft")["digest"])
        source=card("shared",title="Společný původ",summary="Historická technická příručka")
        research.apply(canvas,{"project":"draft","workspace":"draft","key":"source","operations":[source]},"human")
        ref={"projectId":"draft","workspaceId":"draft","id":"shared","revision":1}
        for project,target in (("draft","login"),("draft","isolation"),(other,"access")):
            knowledge.bind(canvas,project,"draft",target,ref,0,False,lambda *args:None,"test")
        query="Jak se prokáže totožnost návštěvníka aplikace?"
        response=knowledge.solutions(canvas,[{"project":"draft","workspace":"draft"},{"project":other,"workspace":"draft"}],query,10,lambda *args:None)
        assert response["retrieval"]["used"]=="hybrid",response["retrieval"]
        assert {solution["solutionRef"]["nodeId"] for solution in response["solutions"]}=={"login","access"},[(item["title"],item["match"]) for item in response["solutions"]]
        assert all(item["match"]["lexical"]==0 and item["match"]["semantic"]>=.82 for item in response["solutions"])
        assert response["comparison"]["commonSources"]==[ref]
        assert all(item["verification"]["status"]=="unknown" for item in response["solutions"])
        assert canvas.db_for("draft").execute("SELECT count(*) FROM research_card_revisions").fetchone()[0]==1
    finally:canvas.close()
