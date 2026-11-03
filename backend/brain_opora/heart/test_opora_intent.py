"""Záměr stránky v nástroji srdce: `intent show`, `propose` (s `--dry-run`) a `diff` nad falešným `/api/flow/*`."""
import json

import pytest

from backend.brain_opora.heart import opora_heart

ENTRY = {"id": "in", "type": "intent.entry", "params": {"from": "menu", "actor": "návštěvník"}}
DONE = {"id": "ok", "type": "intent.done", "params": {"claim": "E-mail odešel", "check": "email"}}
EDGE = {"id": "1", "source_node": "in", "source_port": "main", "target_node": "ok", "target_port": "main", "kind": "main"}
ACTIVE = {"id": "v1", "n": 1, "status": "active", "graph": {"nodes": [ENTRY, DONE], "edges": [EDGE]}}
VIEW = {"id": "view", "type": "intent.view", "params": {"section": "mapa", "shows": "sídlo na mapě"}}
CANDIDATE = {"id": "v2", "n": 2, "status": "candidate",
             "graph": {"nodes": [ENTRY, {**DONE, "params": {"claim": "E-mail odešel do 1 s", "check": "email"}}, VIEW],
                       "edges": [{**EDGE, "target_node": "view"}]}}


@pytest.fixture
def api(monkeypatch, tmp_path):
    state = {"calls": [], "workflows": [], "versions": []}

    def call(method, path, body=None, query=None, actor="heart"):
        state["calls"].append((method, path, body, query))
        if path == "/api/flow/workflows" and method == "GET":
            return {"workflows": state["workflows"]}
        if path == "/api/flow/workflows":
            state["workflows"] = [{"id": "w1", **body}]
            return state["workflows"][0]
        if path.endswith("/versions") and method == "GET":
            return {"versions": state["versions"]}
        if path.endswith("/versions"):
            return {"id": "v9", "n": 9, "status": "draft"}
        if path.endswith("/candidate"):
            return {"id": "v9", "n": 9, "status": "candidate"}
        if path == "/api/flow/graph-check":
            return {"ok": False, "errors": ["Záměr stránky potřebuje aspoň jeden uzel intent.done."]}
        raise AssertionError(path)

    monkeypatch.setattr(opora_heart, "call", call)
    monkeypatch.setenv("OPORA_PROJECT", "p1")
    monkeypatch.chdir(tmp_path)
    return state


def run(capsys, *argv):
    code = opora_heart.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_show_lists_active_and_candidate_compactly(api, capsys):
    code, out = run(capsys, "intent", "show", "kontakt")
    assert code == 0 and out == {"page": "kontakt", "workflowId": None, "active": None, "candidate": None}
    assert api["calls"][0][3] == {"project": "p1", "kind": "page_intent", "owner_ref": "opora:page:kontakt"}
    api["workflows"], api["versions"] = [{"id": "w1"}], [ACTIVE, CANDIDATE]
    code, out = run(capsys, "intent", "show", "kontakt")
    assert out["active"] == {"versionId": "v1", "n": 1,
                             "nodes": ["in · intent.entry · from=menu; actor=návštěvník",
                                       "ok · intent.done · claim=E-mail odešel; check=email"],
                             "edges": ["in.main → ok.main"]}
    assert out["candidate"]["n"] == 2 and "view · intent.view · section=mapa; shows=sídlo na mapě" in out["candidate"]["nodes"]


def test_propose_creates_the_workflow_draft_and_candidate_and_dry_run_only_checks(api, capsys, tmp_path):
    (tmp_path / "zamer.json").write_text(json.dumps({"graph": CANDIDATE["graph"]}), encoding="utf-8")
    code, out = run(capsys, "intent", "propose", "kontakt", "--file", "zamer.json", "--dry-run")
    assert code == 0 and out == {"dryRun": True, "ok": False,
                                 "errors": ["Záměr stránky potřebuje aspoň jeden uzel intent.done."]}
    assert [call[1] for call in api["calls"]] == ["/api/flow/graph-check"]
    assert api["calls"][0][2] == {"kind": "page_intent", "graph": CANDIDATE["graph"]}
    api["calls"].clear()
    code, out = run(capsys, "intent", "propose", "kontakt", "--file", "zamer.json")
    assert code == 0 and out["versionId"] == "v9" and out["status"] == "candidate" and out["workflowId"] == "w1"
    assert [(m, p) for m, p, _, _ in api["calls"]] == [
        ("GET", "/api/flow/workflows"), ("POST", "/api/flow/workflows"), ("POST", "/api/flow/workflows/w1/versions"),
        ("POST", "/api/flow/versions/v9/candidate")]
    assert api["calls"][1][2] == {"kind": "page_intent", "name": "Záměr stránky kontakt", "project_id": "p1",
                                  "owner_ref": "opora:page:kontakt"}
    code, out = run(capsys, "intent", "propose", "kontakt", "--file", "chybi.json")
    assert code == 1 and out["code"] == "intent_file"


def test_diff_compares_candidate_with_the_active_version(api, capsys):
    api["workflows"], api["versions"] = [{"id": "w1"}], [ACTIVE]
    code, out = run(capsys, "intent", "diff", "kontakt")
    assert code == 1 and out["code"] == "intent_no_candidate"
    api["versions"] = [ACTIVE, CANDIDATE]
    code, out = run(capsys, "intent", "diff", "kontakt")
    assert code == 0 and out["activeN"] == 1 and out["candidateN"] == 2
    assert out["nodesAdded"] == ["view · intent.view · section=mapa; shows=sídlo na mapě"] and out["nodesRemoved"] == []
    assert out["nodesChanged"] == ["ok · intent.done · claim=E-mail odešel; check=email ⇒ "
                                   "ok · intent.done · claim=E-mail odešel do 1 s; check=email"]
    assert out["edgesAdded"] == ["in.main → view.main"] and out["edgesRemoved"] == ["in.main → ok.main"]
