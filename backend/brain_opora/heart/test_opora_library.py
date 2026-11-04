"""Knihovna pláten toku v nástroji srdce: `library show|get|save|propose` proti skutečnému API (TestClient s tokenem
srdce), včetně odmítnutí neplatného grafu a hranice knihovny člověka."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.flow.catalogs.test_data_flow import rag


@pytest.fixture
def api(monkeypatch, tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as c:
        pid = c.post("/api/empty-project", headers=HEADERS, json={"name": "Web", "confirmed": True}).json()["id"]
        heart = {**HEADERS, "X-Opora-Actor": "agent; name=heart",
                 tokens.HEADER: tokens.issue_heart(c.app.state.service, pid, "draft")[1]}

        def call(method, path, body=None, query=None, actor="heart"):
            response = c.request(method, path, params=query, json=body, headers=heart)
            if response.status_code >= 400:
                payload = response.json()
                raise opora_heart.Failure(opora_heart.server_failure(response.status_code,
                                                                     payload if isinstance(payload, dict) else {}))
            return response.json()

        monkeypatch.setattr(opora_heart, "call", call)
        monkeypatch.setenv("OPORA_PROJECT", pid)
        monkeypatch.chdir(tmp_path)
        yield c, pid


def run(capsys, *argv):
    code = opora_heart.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_save_checks_the_graph_creates_the_agent_flow_and_activates_it(api, capsys, tmp_path):
    c, pid = api
    broken = {**rag(), "edges": [e for e in rag()["edges"] if e["kind"] != "model"], "groups": []}
    (tmp_path / "broken.json").write_text(json.dumps(broken), encoding="utf-8")
    (tmp_path / "rag.json").write_text(json.dumps(rag()), encoding="utf-8")
    args = ("library", "save", "--folder", "ai-rag", "--slug", "rag", "--title", "RAG – ingest a dotaz")
    code, out = run(capsys, *args, "--file", "broken.json")
    assert code == 1 and out["code"] == "library_graph_check"
    assert out["errors"] == ["Uzel agent: povinný port model není připojený."]
    assert c.get("/api/library", params={"owner": "agent"}).json()["folders"] == []  # nic se neuložilo

    learned = json.dumps({"project": pid, "card": "rag", "result": "verified"})
    code, out = run(capsys, *args, "--file", "rag.json", "--learned-from", learned)
    assert code == 0 and out["created"] is True and out["status"] == "active" and out["n"] == 1
    assert out["ownerRef"] == "opora:library:agent:ai-rag/rag"
    code, again = run(capsys, *args, "--file", "rag.json")
    assert again["created"] is False and again["n"] == 2 and again["flowId"] == out["flowId"]

    code, shown = run(capsys, "library", "show", "--owner", "agent")
    flow = shown["agent"]["folders"][0]
    assert flow["title"] == "AI a RAG" and flow["flows"][0]["activeN"] == 2  # titulek složky převzatý od člověka
    code, graph = run(capsys, "library", "get", out["flowId"], "--version", "1")
    assert graph["meta"]["learnedFrom"]["result"] == "verified" and set(graph["graph"]) == {"nodes", "edges", "notes", "groups", "cases"}


def test_brief_prints_the_generated_markdown_for_active_or_given_version(api, capsys, tmp_path):
    from backend.flow.test_simulate import OK_CASE, bmi_graph

    (tmp_path / "bmi.json").write_text(json.dumps(bmi_graph([OK_CASE])), encoding="utf-8")
    code, saved = run(capsys, "library", "save", "--folder", "functions", "--slug", "bmi", "--title", "Uložit BMI",
                      "--file", "bmi.json")
    assert code == 0
    assert opora_heart.main(["library", "brief", saved["flowId"]]) == 0
    text = capsys.readouterr().out
    assert text.startswith("# Zadání: Uložit BMI") and "opora:library:agent:functions/bmi@1" in text
    assert opora_heart.main(["library", "brief", saved["flowId"], "--version", "7"]) == 1
    assert json.loads(capsys.readouterr().out)["code"]


def test_propose_leaves_a_draft_for_the_human_and_refuses_the_agent_part(api, capsys, tmp_path):
    c, _ = api
    folder = next(f for f in c.get("/api/library").json()["folders"] if f["slug"] == "ai-rag")
    flow = c.post("/api/library/flows", headers=HEADERS, json={"folder": folder["id"], "slug": "rag", "title": "RAG"}).json()
    (tmp_path / "rag.json").write_text(json.dumps(rag()), encoding="utf-8")
    code, out = run(capsys, "library", "propose", flow["id"], "--file", "rag.json", "--note", "Přidat reranker")
    assert code == 0 and out["status"] == "draft"
    versions = c.get(f"/api/library/flows/{flow['id']}").json()["versions"]
    assert [v["status"] for v in versions] == ["draft"] and versions[0]["meta"]["note"] == "Přidat reranker"

    code, saved = run(capsys, "library", "save", "--folder", "ai-rag", "--slug", "x", "--title", "X", "--file", "rag.json")
    code, out = run(capsys, "library", "propose", saved["flowId"], "--file", "rag.json")
    assert code == 1 and out["code"] == "library_not_human"
    code, shown = run(capsys, "library", "show", "--owner", "human", "--folder", "ai-rag")
    assert shown["human"]["folders"][0]["flows"][0]["activeN"] is None and shown["human"]["empty"] == []
