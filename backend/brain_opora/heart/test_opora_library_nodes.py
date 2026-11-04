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
