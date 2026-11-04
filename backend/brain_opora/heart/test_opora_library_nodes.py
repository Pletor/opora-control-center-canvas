"""`library nodes add|set|connect`: kreslení do draftu přes skutečné API (fixture z `test_opora_library.py`)."""
import json

from backend.brain_opora.heart.test_opora_library import api, run  # noqa: F401  (fixture api)
from backend.canvas.test_canvas_plan import HEADERS


def human_flow(c, slug="bmi"):
    folder = next(f for f in c.get("/api/library").json()["folders"] if f["slug"] == "ai-rag")
    return c.post("/api/library/flows", headers=HEADERS, json={"folder": folder["id"], "slug": slug, "title": "BMI"}).json()


def drafts(c, flow):
    return [v for v in c.get(f"/api/library/flows/{flow['id']}").json()["versions"] if v["status"] == "draft"]


def test_add_places_nodes_by_layer_lane_and_after_chain(api, capsys):
    c, _ = api
    flow = human_flow(c)
    code, form = run(capsys, "library", "nodes", "add", flow["id"], "--type", "fe.form")
    assert code == 0 and form["nodeId"] == "fe-form-1" and form["status"] == "draft"
    code, endpoint = run(capsys, "library", "nodes", "add", flow["id"], "--type", "be.endpoint", "--after", "fe-form-1")
    code, write = run(capsys, "library", "nodes", "add", flow["id"], "--type", "db.write", "--title", "Zápis měření")
    code, shown = run(capsys, "library", "get", flow["id"], "--version", str(write["n"]))
    pos = {n["id"]: n["position"] for n in shown["graph"]["nodes"]}
    assert pos == {"fe-form-1": {"x": 0, "y": 0}, "be-endpoint-1": {"x": 146, "y": 186},
                   "db-write-1": {"x": 292, "y": 372}}
    note = next(n for n in shown["graph"]["nodes"] if n["id"] == "db-write-1")
    assert note["notes"] == "Zápis měření" and "layer" not in note
    assert endpoint["n"] == 2 and write["n"] == 3  # každá změna = nový draft z nejnovějšího


def test_custom_step_needs_layer_title_and_branches_make_ports(api, capsys):
    c, _ = api
    flow = human_flow(c)
    code, out = run(capsys, "library", "nodes", "add", flow["id"], "--type", "custom.step", "--branches", "ok,chyba",
                    "--layer", "be", "--title", "Spočítej BMI")
    assert code == 0
    code, other = run(capsys, "library", "nodes", "add", flow["id"], "--type", "fe.notify", "--layer", "fe")
    code, out = run(capsys, "library", "nodes", "connect", flow["id"], "--from", "custom-step-1", "--from-port", "chyba",
                    "--to", "fe-notify-1", "--via", "http", "--kind", "json")
    assert code == 0 and out["edgeId"] == "e-1"
    code, out = run(capsys, "library", "nodes", "connect", flow["id"], "--from", "custom-step-1", "--from-port", "main",
                    "--to", "fe-notify-1")
    assert code == 1 and "nemá out port 'main'" in out["errors"][0]


def test_graph_errors_leave_the_draft_untouched(api, capsys, tmp_path):
    c, _ = api
    flow = human_flow(c)
    run(capsys, "library", "nodes", "add", flow["id"], "--type", "fe.click")
    before = drafts(c, flow)
    code, out = run(capsys, "library", "nodes", "add", flow["id"], "--type", "custom.step")
    assert code == 1 and out["code"] == "library_graph_check"
    assert out["errors"] == ["Uzel custom-step-1: krok na míru (custom.step) musí mít neprázdný titulek (params.title)."]
    (tmp_path / "bad.json").write_text(json.dumps({"layer": "xx"}), encoding="utf-8")
    code, out = run(capsys, "library", "nodes", "set", flow["id"], "fe-click-1", "--file", "bad.json")
    assert code == 1 and out["errors"] == ["Uzel fe-click-1: layer je fe | be | db | infra | ai | neutral."]
    code, out = run(capsys, "library", "nodes", "add", flow["id"], "--type", "nope")
    assert out["code"] == "library_node_type"
    code, out = run(capsys, "library", "nodes", "add", flow["id"], "--type", "fe.show", "--after", "zzz")
    assert out["code"] == "library_node_missing"
    code, out = run(capsys, "library", "nodes", "connect", flow["id"], "--from", "fe-click-1", "--to", "zzz")
    assert out["code"] == "library_node_missing"
    assert drafts(c, flow) == before


def test_connect_stores_schema_and_example_and_rejects_incompatible_kind(api, capsys):
    c, _ = api
    flow = human_flow(c)
    for kind in ("fe.form", "be.endpoint", "db.read"):
        run(capsys, "library", "nodes", "add", flow["id"], "--type", kind)
    code, out = run(capsys, "library", "nodes", "connect", flow["id"], "--from", "fe-form-1", "--to", "be-endpoint-1",
                    "--via", "http", "--kind", "json", "--schema", '{"type":"object"}', "--example", '[1, "a"]')
    assert code == 0
    _, shown = run(capsys, "library", "get", flow["id"], "--version", str(out["n"]))  # uložená verze data drží
    assert shown["graph"]["edges"][0]["data"] == {"kind": "json", "schema": {"type": "object"}, "example": [1, "a"]}
    code, out = run(capsys, "library", "nodes", "connect", flow["id"], "--from", "be-endpoint-1", "--to", "db-read-1",
                    "--kind", "json", "--example", "{nope")
    assert code == 1 and out["code"] == "library_edge_example"
    code, out = run(capsys, "library", "nodes", "connect", flow["id"], "--from", "db-read-1", "--to", "be-endpoint-1")
    assert code == 1 and "be-endpoint-1 nepřijímá data druhu 'table' (přijímá: json, event)" in out["errors"][0]


def test_set_changes_the_node_and_agent_flow_stays_writable_but_not_active(api, capsys, tmp_path):
    c, _ = api
    flow = human_flow(c)
    run(capsys, "library", "nodes", "add", flow["id"], "--type", "fe.form")
    (tmp_path / "patch.json").write_text(json.dumps({"layer": "be", "notes": "Přepsáno"}), encoding="utf-8")
    code, out = run(capsys, "library", "nodes", "set", flow["id"], "fe-form-1", "--file", "patch.json")
    code, shown = run(capsys, "library", "get", flow["id"], "--version", str(out["n"]))
    assert shown["graph"]["nodes"][0]["layer"] == "be" and shown["graph"]["nodes"][0]["notes"] == "Přepsáno"
    assert shown["status"] == "draft"  # aktivovat v knihovně člověka srdce nesmí
    assert c.post(f"/api/flow/versions/{out['versionId']}/activate", json={}, headers={"X-Opora-Actor": "agent; name=x"}
                  ).status_code >= 400
    assert [v["status"] for v in c.get(f"/api/library/flows/{flow['id']}").json()["versions"]][-1] == "draft"


def test_case_add_and_run_use_the_draft_and_the_simulator(api, capsys, tmp_path):
    from backend.flow.test_simulate import BAD_CASE, OK_CASE, bmi_graph

    c, _ = api
    flow = human_flow(c)
    (tmp_path / "graph.json").write_text(json.dumps(bmi_graph()), encoding="utf-8")
    code, proposed = run(capsys, "library", "propose", flow["id"], "--file", "graph.json")
    assert code == 0
    (tmp_path / "ok.json").write_text(json.dumps(OK_CASE), encoding="utf-8")
    (tmp_path / "bad.json").write_text(json.dumps(BAD_CASE), encoding="utf-8")
    code, added = run(capsys, "library", "case", "add", flow["id"], "--file", "ok.json")
    assert code == 0 and added["caseId"] == "ok" and added["n"] == proposed["n"] + 1
    code, added = run(capsys, "library", "case", "add", flow["id"], "--file", "bad.json")
    code, again = run(capsys, "library", "case", "add", flow["id"], "--file", "ok.json")  # stejné id = nahradí
    code, shown = run(capsys, "library", "get", flow["id"], "--version", str(again["n"]))
    assert [x["id"] for x in shown["graph"]["cases"]] == ["bad", "ok"]

    code, ran = run(capsys, "library", "case", "run", flow["id"], "--case", "ok")
    assert code == 0 and ran["ok"] and ran["expect"] == {"ok": True, "diffs": []} and ran["trace"][3]["out"]["bmi"] == 24.7
    code, ran = run(capsys, "library", "case", "run", flow["id"], "--case", "bad")
    assert ran["notify"] == "Neplatná výška" and ran["trace"][2]["branch"] == "false"
    code, missing = run(capsys, "library", "case", "run", flow["id"], "--case", "nic")
    assert code == 1 and "nemá případ" in json.dumps(missing, ensure_ascii=False)
    (tmp_path / "wrong.json").write_text(json.dumps({**OK_CASE, "id": "w", "start": "nope"}), encoding="utf-8")
    code, refused = run(capsys, "library", "case", "add", flow["id"], "--file", "wrong.json")
    assert code == 1 and refused["code"] == "library_graph_check"
    assert refused["errors"] == ["Případ w: start 'nope' není uzel grafu."]
