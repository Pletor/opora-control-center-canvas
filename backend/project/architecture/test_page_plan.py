import copy

import pytest

from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService
from backend.project.architecture import page_plan

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
SCOPE = ("draft", "draft")


def box(identifier, role="content", **extra):
    return {"id": identifier, "role": role, "name": identifier.title(), "intent": ""} | extra


def graph():
    def node(identifier, parent, **extra):
        return {"id": identifier, "parentId": parent, "kind": "node", "name": identifier.title(), "purpose": "",
                "x": 0, "y": 0} | extra
    return {"nodes": [
        {"id": "app", "parentId": None, "kind": "sector", "name": "Web", "purpose": "", "x": 0, "y": 0,
         "site": {"kind": "application", "environments": []}},
        node("kurz", "app", site={"kind": "page", "path": "/kurz", "goal": "Koupit kurz.", "sections": [
            box("header", "header", box={"x": 0, "y": 0, "w": 12, "h": 2}),
            box("cta", "cta", status="approved", source="human")]}),
        node("koupit", "kurz", element={"kind": "action"}, card={"section": "cta", "status": "ready"}),
        node("clen", "kurz", element={"kind": "actor"}),
        node("stara", "kurz"),  # starší karta bez element: do logiky nepatří
        node("prazdna", "app", site={"kind": "page", "path": "/prazdna"}),
    ], "edges": []}


@pytest.fixture
def canvas(tmp_path):
    service = CanvasService(tmp_path / "data")
    service.save_graph(*SCOPE, graph(), service.view(*SCOPE)["digest"])
    yield service
    service.close()


def payload(canvas, sections, **extra):
    digest = page_plan.read(canvas, *SCOPE, "kurz")["digest"]
    return {"project": "draft", "workspace": "draft", "pageId": "kurz", "expectedDigest": digest,
            "sections": sections, **extra}


def test_read_composes_layout_sketch_and_logic(canvas):
    canvas.drawing(*SCOPE, "box/kurz/cta", {"project": "draft", "workspace": "draft", "layer": "box/kurz/cta",
                                            "expected_revision": 0, "scene": {"elements": []}})
    plan = page_plan.read(canvas, *SCOPE, "kurz")
    assert plan["page"] == {"id": "kurz", "name": "Kurz", "path": "/kurz", "goal": "Koupit kurz."}
    assert [(item["id"], item["sketch"]) for item in plan["sections"]] == [("header", None), ("cta", {"revision": 1})]
    assert plan["logic"] == [
        {"id": "koupit", "kind": "action", "name": "Koupit", "purpose": "", "section": "cta", "milestone": "Realizace"},
        {"id": "clen", "kind": "actor", "name": "Clen", "purpose": "", "section": None, "milestone": "Návrh"}]
    assert plan["digest"] == page_plan.plan_digest(graph()["nodes"][1]["site"]["sections"])
    empty = page_plan.read(canvas, *SCOPE, "prazdna")
    assert (empty["sections"], empty["logic"]) == ([], [])
    for missing in ("nikdo", "koupit"):
        with pytest.raises(GateError) as refused:
            page_plan.read(canvas, *SCOPE, missing)
        assert refused.value.status == 404


def test_human_save_stamps_source_and_keeps_unchanged_boxes(canvas):
    sections = copy.deepcopy(page_plan.read(canvas, *SCOPE, "kurz")["sections"])
    sections[0]["box"] = {"x": 0, "y": 0, "w": 12, "h": 3}
    sections.append(box("hero", "hero", source="scan"))  # klientský source server přepíše
    saved = page_plan.save(canvas, payload(canvas, sections), "human")
    assert [(item["id"], item.get("source")) for item in saved["sections"]] == [
        ("header", "human"), ("cta", "human"), ("hero", "human")]
    assert saved["sections"][1]["status"] == "approved"
    with pytest.raises(GateError) as stale:
        page_plan.save(canvas, {**payload(canvas, []), "expectedDigest": "x"}, "human")
    assert stale.value.status == 409 and stale.value.code == "plan_changed"
    cleared = page_plan.save(canvas, payload(canvas, []), "human")
    assert cleared["sections"] == [] and "sections" not in canvas.view(*SCOPE)["graph"]["nodes"][1]["site"]


def test_digest_ignores_other_cards(canvas):
    before = payload(canvas, [box("a")])
    view = canvas.view(*SCOPE)
    moved = {"nodes": [{**node, "x": 50} if node["id"] == "koupit" else node for node in view["graph"]["nodes"]],
             "edges": view["graph"]["edges"]}
    canvas.save_graph(*SCOPE, moved, view["digest"])
    assert page_plan.save(canvas, before, "human")["sections"][0]["id"] == "a"


def test_agent_writes_only_proposed_and_never_touches_approved(canvas):
    current = page_plan.read(canvas, *SCOPE, "kurz")["sections"]
    header, cta = current
    saved = page_plan.save(canvas, payload(canvas, [header, cta, box("hero", "hero", status="proposed")]), "agent")
    assert saved["sections"][2]["source"] == "agent" and saved["sections"][0].get("source") is None
    for sections, message in (
            ([header, cta, box("x")], "proposed"),
            ([header, cta | {"name": "Jinak", "status": "proposed"}], "schválil"),
            ([header], "nesmaže")):
        with pytest.raises(GateError, match=message) as refused:
            page_plan.save(canvas, payload(canvas, sections), "agent")
        assert refused.value.status == 403
    changed = page_plan.save(canvas, payload(canvas, [header | {"status": "proposed", "name": "Nová"}, cta]), "agent")
    assert changed["sections"][0]["source"] == "agent"


def test_scan_boxes_get_scan_source(canvas):
    hero = box("hero", "hero", status="proposed")
    saved = page_plan.save(canvas, payload(canvas, [hero, box("x", status="proposed")]), "human", [hero])
    assert [item["source"] for item in saved["sections"]] == ["scan", "human"]


def test_inspiration_files_must_exist(canvas):
    with pytest.raises(GateError) as missing:
        page_plan.save(canvas, payload(canvas, [box("a", inspiration={"files": ["f1"]})]), "human")
    assert missing.value.code == "file_not_found"
    canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "f1", "mimeType": "image/png",
                                                                           "dataURL": PNG}})
    saved = page_plan.save(canvas, payload(canvas, [box("a", inspiration={"files": ["f1"], "url": "https://x.cz"})]),
                           "human")
    assert saved["sections"][0]["inspiration"] == {"files": ["f1"], "url": "https://x.cz"}


def test_invalid_layout_is_rejected_by_site_metadata(canvas):
    with pytest.raises(ValueError, match="box"):
        page_plan.save(canvas, payload(canvas, [box("a", box={"x": 11, "y": 0, "w": 2, "h": 1})]), "human")
    with pytest.raises(GateError):
        page_plan.save(canvas, payload(canvas, ["a"]), "human")


def test_set_status_approves_and_drafts_a_box(canvas):
    scope = {"project": "draft", "workspace": "draft"}
    approved = page_plan.set_status(canvas, {**scope, "status": "approved"}, "kurz", "header")
    assert approved["sections"][0]["status"] == "approved"
    drafted = page_plan.set_status(canvas, {**scope, "status": "draft", "expectedDigest": approved["digest"]},
                                   "kurz", "header")
    assert drafted["sections"][0]["status"] == "draft"
    for body, section, code in (({**scope, "status": "proposed"}, "header", "invalid_payload"),
                                ({**scope, "status": "draft"}, "nic", "box_not_found"),
                                ({**scope, "status": "draft", "expectedDigest": "x"}, "header", "plan_changed")):
        with pytest.raises(GateError) as refused:
            page_plan.set_status(canvas, body, "kurz", section)
        assert refused.value.code == code


def test_brief_is_short_layout_and_logic():
    plan = page_plan.brief(graph(), "kurz")
    assert plan["layout"] == ["header: header „Header“ [0,0 12×2] draft", "cta: cta „Cta“ approved"]
    assert plan["logic"] == ["action „Koupit“ → Cta", "actor „Clen“ → celá stránka"]
    assert page_plan.brief(graph(), "prazdna") is None
