import json
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.editor.storyboard.storyboard import ANIMATIONS, MOMENT_ID, StoryboardService, animation_layers, validate_storyboard

GRAPH = {
    "nodes": [
        {"id": "sektor", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
        {"id": "karta", "parentId": "sektor", "kind": "node", "name": "Karta", "purpose": "", "x": 0, "y": 0},
    ],
    "edges": [],
}


def board(**changes):
    data = {
        "animation": "kulicka", "title": "Odraz", "duration": 12,
        "moments": [
            {"t": 5, "title": "Pozdě"},
            {"t": 2.3, "title": "Dopad", "comment": "Plošší.", "state": {"x": 0.5, "color": "#f4b942", "contact": True},
             "annotations": [
                 {"kind": "arrow", "from": {"x": 0.5, "y": 0.72}, "to": {"x": 0.56, "y": 0.42}, "text": "odraz sem"},
                 {"kind": "note", "at": {"x": 0.5, "y": 0.8}, "text": "stín"}]},
        ],
    }
    data.update(changes)
    return data


def payload(storyboard, revision=0, node="karta"):
    return {"project": "draft", "workspace": "draft", "nodeId": node, "expected_revision": revision, "storyboard": storyboard}


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.save_graph("draft", "draft", GRAPH, canvas.view("draft", "draft")["digest"])
    return StoryboardService(canvas)


def test_validate_defaults_sorts_and_drops_unknown_keys():
    clean = validate_storyboard(board(junk=1))
    assert [m["t"] for m in clean["moments"]] == [2.3, 5]
    assert clean["fps"] == 60 and clean["size"] == {"w": 1920, "h": 1080} and clean["ground"] == 0.8
    assert clean["background"] == "#101418" and clean["schema"] == "opora.storyboard/1" and "junk" not in clean
    assert clean["moments"][1]["ease"] == "linear" and clean["moments"][1]["state"] == {} and clean["moments"][1]["annotations"] == []


NOTE = {"kind": "note", "at": {"x": 0, "y": 0}, "text": ""}


@pytest.mark.parametrize("changes", [
    {"animation": "nic"}, {"duration": 0.5}, {"duration": 121}, {"fps": 23}, {"fps": 61},
    {"size": {"w": 100, "h": 1080}}, {"size": {"w": 1920, "h": 5000}}, {"moments": []},
    {"moments": [{"t": 0}] * 201}, {"moments": [{"t": 13}]}, {"moments": [{"t": -1}]},
    {"moments": [{"t": 1, "title": "x" * 501}]}, {"moments": [{"t": 1, "comment": "x" * 2001}]},
    {"moments": [{"t": 1, "ease": "zvlastni"}]},
    {"moments": [{"t": 1, "state": {f"k{i}": 1 for i in range(33)}}]},
    {"moments": [{"t": 1, "state": {"x": float("inf")}}]},
    {"moments": [{"t": 1, "state": {"x": "y" * 101}}]},
    {"moments": [{"t": 1, "state": {"x": [1]}}]},
    {"moments": [{"t": 1, "annotations": [NOTE] * 21}]},
    {"moments": [{"t": 1, "annotations": [{**NOTE, "at": {"x": 1.1, "y": 0}}]}]},
    {"moments": [{"t": 1, "annotations": [{**NOTE, "text": "x" * 201}]}]},
    {"moments": [{"t": 1, "annotations": [{"kind": "kruh"}]}]},
    {"schema": "jine/1"},
])
def test_validate_rejects_out_of_bounds(changes):
    with pytest.raises(ValueError):
        validate_storyboard(board(**changes))


def test_validate_accepts_bounds():
    clean = validate_storyboard(board(duration=120, fps=24, size={"w": 320, "h": 4096}, moments=[{"t": 0}, {"t": 120}]))
    assert clean["duration"] == 120 and len(clean["moments"]) == 2


def test_read_without_file(service):
    result = service.read("draft", "draft", "karta")
    assert result["storyboard"] is None and result["revision"] == 0 and result["readOnly"] is False
    assert result["animations"] == [{"id": key, "label": label} for key, label in ANIMATIONS.items()]


def test_save_read_revision_conflict_and_delete(service):
    assert service.save(payload(board())) == {"revision": 1}
    stored = service.read("draft", "draft", "karta")
    assert stored["revision"] == 1 and stored["storyboard"]["revision"] == 1 and stored["storyboard"]["updatedAt"].endswith("Z")
    with pytest.raises(ValueError, match="změnil v jiném okně"):
        service.save(payload(board(), revision=0))
    assert service.save(payload(board(title="Nový"), revision=1)) == {"revision": 2}
    assert service.read("draft", "draft", "karta")["storyboard"]["title"] == "Nový"
    service.save(payload(None, revision=2))
    gone = service.read("draft", "draft", "karta")
    assert gone["storyboard"] is None and gone["revision"] == 3  # náhrobek: smazání nevrací revizi na 0 (ABA)
    with pytest.raises(ValueError, match="změnil v jiném okně"):
        service.save(payload(board(), revision=0))
    assert service.save(payload(board(), revision=3)) == {"revision": 4}
    assert service.brief_section("draft", "draft", "karta") is not None


def test_save_rejects_bad_targets_and_payloads(service):
    with pytest.raises(ValueError, match="neexistuje"):
        service.save(payload(board(), node="zadny"))
    with pytest.raises(ValueError, match="kartě"):
        service.save(payload(board(), node="sektor"))
    with pytest.raises(ValueError, match="formát"):
        service.save({"project": "draft"})
    with pytest.raises(ValueError):
        service.save({**payload(board()), "project": "neznamy"})


def test_read_only_workspace_refuses_write(service):
    class Main:
        def __init__(self, canvas):
            self.canvas = canvas

        def view(self, pid, wid):
            return {**self.canvas.view(pid, wid), "readOnly": True}

        def __getattr__(self, name):
            return getattr(self.canvas, name)

    guarded = StoryboardService(Main(service.canvas))
    assert guarded.read("draft", "draft", "karta")["readOnly"] is True
    with pytest.raises(ValueError, match="Main je pouze pro čtení."):
        guarded.save(payload(board()))


def test_brief_section(service):
    assert service.brief_section("draft", "draft", "karta") is None
    service.save(payload(board()))
    section = service.brief_section("draft", "draft", "karta")
    assert section["animation"] == "kulicka" and section["duration"] == 12
    first = section["moments"][0]
    assert first["comment"] == "Plošší." and first["state"]["contact"] is True
    assert first["annotationsText"] == [
        "šipka z (0.50, 0.72) do (0.56, 0.42): odraz sem",
        "poznámka u (0.50, 0.80): stín",
    ]
    assert section["moments"][1]["annotationsText"] == []


PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
MOMENT = "m-3f9a1c2e"
LAYER = f"sb/karta/{MOMENT}"


def sketched(**sketch):
    return board(moments=[{"t": 1, "id": MOMENT, "sketch": {"layer": LAYER, "fileId": "f1", **sketch}}, {"t": 2}])


def test_moment_ids_are_filled_kept_and_unique():
    clean = validate_storyboard(board(moments=[{"t": 1, "id": MOMENT}, {"t": 2, "id": MOMENT}, {"t": 3, "id": "zle"}, {"t": 4}]))
    ids = [m["id"] for m in clean["moments"]]
    assert ids[0] == MOMENT and len(set(ids)) == 4
    assert all(i.startswith("m-") and len(i) == 10 for i in ids)


def test_sketch_validation_and_legacy_text_dropped():
    clean = validate_storyboard(sketched(), "karta")
    assert clean["moments"][0]["sketch"] == {"layer": LAYER, "fileId": "f1", "imageStale": False}
    assert "sketch" not in clean["moments"][1]
    old = validate_storyboard(board(moments=[{"t": 1, "sketch": "stará poznámka"}]))
    assert "sketch" not in old["moments"][0]
    for bad in ({"layer": "sb/jina/" + MOMENT}, {"layer": f"sb/karta/m-00000000"}, {"layer": "karta"}, {"fileId": ""}, {"fileId": "x" * 81}, {"fileId": "", "imageStale": False}, {"fileId": "a/b"}):
        with pytest.raises(ValueError):
            validate_storyboard(sketched(**bad), "karta")
    with pytest.raises(ValueError):
        validate_storyboard(sketched(layer="sb/jina/" + MOMENT), "karta")


def test_sketch_layers_and_mark_stale(service):
    service.canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "f1", "mimeType": "image/png", "dataURL": PNG}})
    service.save(payload(sketched()))
    assert LAYER in service.sketch_layers("draft", "draft", "karta") and len(service.sketch_layers("draft", "draft", "karta")) == 2
    service.mark_sketch_stale("draft", "draft", "karta", MOMENT)
    stored = service.read("draft", "draft", "karta")
    assert stored["revision"] == 2 and stored["storyboard"]["moments"][0]["sketch"]["imageStale"] is True
    assert validate_storyboard(sketched(fileId="", imageStale=True), "karta")["moments"][0]["sketch"]["fileId"] == ""
    service.mark_sketch_stale("draft", "draft", "karta", "m-ffffffff")
    assert service.read("draft", "draft", "karta")["revision"] == 2
    assert service.sketch_layers("draft", "draft", "sektor") == set()
    second = service.read("draft", "draft", "karta")["storyboard"]["moments"][1]["id"]
    assert "sketch" not in service.read("draft", "draft", "karta")["storyboard"]["moments"][1]
    service.mark_sketch_stale("draft", "draft", "karta", second)
    created = service.read("draft", "draft", "karta")["storyboard"]["moments"][1]["sketch"]
    assert created == {"layer": f"sb/karta/{second}", "fileId": "", "imageStale": True}


def test_brief_section_sketch_summary(service):
    service.canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "f1", "mimeType": "image/png", "dataURL": PNG}})
    service.save(payload(sketched()))
    service.canvas.sketch_layers_provider = service.sketch_layers
    assert service.brief_section("draft", "draft", "karta")["moments"][0]["sketch"]["summary"] == ""
    el = {"x": 0, "y": 0, "width": 10, "height": 10}
    scene = {"elements": [
        {"id": "a1", "type": "arrow", "points": [[0, 0], [1, 1]], **el}, {"id": "a2", "type": "arrow", "points": [[0, 0], [1, 1]], **el},
        {"id": "a3", "type": "arrow", "points": [[0, 0], [1, 1]], **el},
        {"id": "t1", "type": "text", "text": "tady zrychlit", **el}, {"id": "t2", "type": "text", "text": "y" * 100, **el},
        {"id": "f1", "type": "freedraw", "points": [[0, 0]], **el},
        {"id": "bg", "type": "rectangle", "customData": {"storyboardBackdrop": True}, **el}]}
    service.canvas.drawing("draft", "draft", LAYER, {"project": "draft", "workspace": "draft", "layer": LAYER,
                                                    "expected_revision": 0, "scene": scene})
    sketch = service.brief_section("draft", "draft", "karta")["moments"][0]["sketch"]
    assert sketch["summary"] == f"3 šipky, 2 texty, 1 kresba: „tady zrychlit“, „{'y' * 80}“"
    assert sketch["layer"] == LAYER and service.brief_section("draft", "draft", "karta")["moments"][1]["sketch"] == ""



def test_read_backfills_moment_ids_for_older_storyboards(service):
    """Storyboard uložený před zavedením `id` dostane id momentů při prvním čtení a zůstane stejná revize."""
    path = service._path("draft", "draft", "karta")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "opora.storyboard/1", "animation": "kulicka", "duration": 2,
                                "moments": [{"t": 0, "title": "a"}, {"t": 1, "title": "b"}], "revision": 4}),
                    encoding="utf-8")
    first = service.read("draft", "draft", "karta")
    ids = [m["id"] for m in first["storyboard"]["moments"]]
    assert all(MOMENT_ID.fullmatch(i) for i in ids) and len(set(ids)) == 2
    assert first["revision"] == 4
    second = service.read("draft", "draft", "karta")
    assert [m["id"] for m in second["storyboard"]["moments"]] == ids


CODE = {"source": "export const layers = [];\nexport function paint() {}", "fields": [{"key": "x", "kind": "number", "label": "X", "min": 0, "max": 1}],
        "layers": [{"id": "ball", "label": "Kulička"}], "title": "Vlastní"}


def test_code_animation_validation():
    clean = validate_storyboard(board(animation="kod", code=CODE))
    assert clean["code"]["source"] == CODE["source"] and clean["code"]["fields"][0]["max"] == 1
    assert "code" not in validate_storyboard(board(code=CODE))
    bad = [None, {**CODE, "source": ""}, {**CODE, "source": "x" * 65537}, {**CODE, "source": "a\x00b"},
           {**CODE, "fields": [{"key": "X", "kind": "number"}]}, {**CODE, "fields": [{"key": "x", "kind": "date"}]},
           {**CODE, "fields": [{"key": "x", "kind": "number"}] * 33}, {**CODE, "layers": []}, {**CODE, "layers": [{"id": "A"}]},
           {**CODE, "layers": [{"id": "a"}] * 17}, {**CODE, "title": "t" * 121}]
    for code in bad:
        with pytest.raises(ValueError):
            validate_storyboard(board(animation="kod", code=code))
    with pytest.raises(ValueError):
        validate_storyboard(board(animation="kod"))
    assert validate_storyboard(board(animation="kod", code={**CODE, "source": "x" * 65536, "fields": []}))


SCENE = {"html": "<!doctype html><html><body><div data-layer=\"koule\"></div></body></html>",
         "fields": [{"key": "glow", "kind": "number", "label": "Záře", "min": 0, "max": 1, "step": 0.01}],
         "layers": [{"id": "pozadi", "label": "Pozadí"}, {"id": "koule", "label": "Koule"}], "title": "Web"}


def test_scene_animation_validation_and_layers():
    clean = validate_storyboard(board(animation="scena", scene=SCENE))
    assert clean["scene"]["html"] == SCENE["html"] and clean["scene"]["fields"][0]["max"] == 1
    assert "scene" not in validate_storyboard(board(scene=SCENE))
    assert animation_layers(clean) == ("pozadi", "koule")
    tab = {**SCENE, "html": "a\tb\r\n"}
    assert validate_storyboard(board(animation="scena", scene=tab))["scene"]["html"] == "a\tb\r\n"
    assert validate_storyboard(board(animation="scena", scene=SCENE, assets=[asset(target="koule")]))["assets"][0]["target"] == "koule"
    with pytest.raises(ValueError, match="cílová vrstva „kulicka“ v animaci není"):
        validate_storyboard(board(animation="scena", scene=SCENE, assets=[asset(target="kulicka")]))
    with pytest.raises(ValueError, match="vyžaduje objekt scene"):
        validate_storyboard(board(animation="scena"))
    with pytest.raises(ValueError, match="1–262144"):
        validate_storyboard(board(animation="scena", scene={**SCENE, "html": "x" * 262145}))
    assert validate_storyboard(board(animation="scena", scene={**SCENE, "html": "x" * 262144}))
    with pytest.raises(ValueError, match="řídicí znaky"):
        validate_storyboard(board(animation="scena", scene={**SCENE, "html": "a\x00b"}))
    for scene in [{**SCENE, "html": ""}, {**SCENE, "layers": []}, {**SCENE, "layers": [{"id": "a"}] * 17},
                  {**SCENE, "fields": [{"key": "x", "kind": "number"}] * 33}, {**SCENE, "title": "t" * 121}]:
        with pytest.raises(ValueError):
            validate_storyboard(board(animation="scena", scene=scene))


def test_brief_section_scene(service):
    service.save(payload(board(animation="scena", scene=SCENE)))
    section = service.brief_section("draft", "draft", "karta")
    assert section["animation"] == "scena" and section["layers"] == ["pozadi", "koule"]
    assert section["scene"]["html"] == SCENE["html"] and section["scene"]["title"] == "Web"
    assert section["scene"]["layers"] == SCENE["layers"] and "code" not in section


def test_answered_flag_default_kept_and_validated():
    clean = validate_storyboard(board(moments=[{"t": 1}, {"t": 2, "answered": True}]))
    assert [m["answered"] for m in clean["moments"]] == [False, True]
    with pytest.raises(ValueError):
        validate_storyboard(board(moments=[{"t": 1, "answered": "ano"}]))


def test_brief_section_code_and_workflow(service):
    # První zápis: `answered: true` bez uloženého protějšku se neuzná (vstup člověka je nový).
    service.save(payload(board(animation="kod", code=CODE, moments=[
        {"t": 1, "title": "A", "comment": "x"}, {"t": 2, "title": "B", "comment": "y", "answered": True}, {"t": 3, "title": "C"}])))
    section = service.brief_section("draft", "draft", "karta")
    assert section["code"] == CODE and section["layers"] == ["ball"] and section["assets"] == []
    assert [m["answered"] for m in section["moments"]] == [False, False, False]
    assert all(MOMENT_ID.fullmatch(m["id"]) for m in section["moments"])
    assert section["workflow"] == {"openComments": 2, "openAssets": 0, "next": "Reaguj na 2 momentů s novým komentářem: t=1 s „A“, t=2 s „B“"}
    # Agent odpoví se stejnými id a nezměněným komentářem: answered drží.
    moments = [{**m, "answered": True} for m in section["moments"]]
    service.save(payload(board(animation="kod", code=CODE, moments=moments), revision=1))
    section = service.brief_section("draft", "draft", "karta")
    assert [m["answered"] for m in section["moments"]] == [True, True, True]
    assert section["workflow"]["openComments"] == 0 and section["workflow"]["openAssets"] == 0
    assert section["workflow"]["next"].startswith("Žádný nový komentář; čekej na člověka. Storyboard naposledy uložen ") and "(revize 2)" in section["workflow"]["next"]
    assert section["revision"] == 2 and section["updatedAt"]
    # Člověk změní komentář (i kdyby answered zůstalo true): backend moment znovu otevře.
    moments[0] = {**moments[0], "comment": "x jinak"}
    service.save(payload(board(animation="kod", code=CODE, moments=moments), revision=2))
    section = service.brief_section("draft", "draft", "karta")
    assert [m["answered"] for m in section["moments"]] == [False, True, True]
    # Šipka bez komentáře je také vstup člověka.
    moments[0] = {**moments[0], "answered": False}  # jako frontend: změněný komentář člověk neoznačí za vyřízený
    moments[2] = {**moments[2], "annotations": [NOTE]}
    service.save(payload(board(animation="kod", code=CODE, moments=moments), revision=3))
    assert [m["answered"] for m in service.brief_section("draft", "draft", "karta")["moments"]] == [False, True, False]


def test_sketch_change_reopens_moment(service):
    service.canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "f1", "mimeType": "image/png", "dataURL": PNG}})
    service.canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "f2", "mimeType": "image/png", "dataURL": PNG}})
    service.save(payload(sketched()))
    stored = service.read("draft", "draft", "karta")["storyboard"]
    stored["moments"][0]["answered"] = True
    service.save(payload(stored, revision=1))
    assert service.read("draft", "draft", "karta")["storyboard"]["moments"][0]["answered"] is True
    service.mark_sketch_stale("draft", "draft", "karta", MOMENT)
    assert service.read("draft", "draft", "karta")["storyboard"]["moments"][0]["answered"] is False
    stored = service.read("draft", "draft", "karta")["storyboard"]
    stored["moments"][0]["answered"] = True
    stored["moments"][0]["sketch"] = {"layer": LAYER, "fileId": "f2", "imageStale": False}
    service.save(payload(stored, revision=stored["revision"]))
    assert service.read("draft", "draft", "karta")["storyboard"]["moments"][0]["answered"] is False



def asset(**changes):
    data = {"id": "a-12345678", "name": "šachovnice", "fileId": "tex1", "mimeType": "image/png", "purpose": "texture",
            "target": "ball", "color": "#ff0000", "colorUse": "tint", "note": "na kouli"}
    data.update(changes)
    return data


def test_asset_validation_rejects_unknown_targets_and_bad_shapes():
    clean = validate_storyboard(board(animation="kod", code=CODE, moments=[{"t": 1, "id": MOMENT}], assets=[asset(momentId=MOMENT)]))
    assert clean["assets"][0] == {**asset(momentId=MOMENT), "answered": False}
    assert validate_storyboard(board())["assets"] == []
    assert validate_storyboard(board(assets=[asset(target="kulicka")]))["assets"][0]["target"] == "kulicka"
    bad = [asset(target="koule"), asset(momentId="m-00000000"), asset(fileId=""), asset(fileId="a/b"), asset(mimeType="image/svg+xml"),
           asset(purpose="logo"), asset(color="red"), asset(color="#ff0000", colorUse=""), asset(colorUse="glow"), asset(note="x" * 501), "text"]
    for item in bad:
        with pytest.raises(ValueError):
            validate_storyboard(board(animation="kod", code=CODE, assets=[item]))
    with pytest.raises(ValueError, match="cílová vrstva „koule“ v animaci není. Vrstvy: ball"):
        validate_storyboard(board(animation="kod", code=CODE, assets=[asset(target="koule")]))
    with pytest.raises(ValueError, match="nejvýše 16"):
        validate_storyboard(board(assets=[asset(target="")] * 17))
    ids = [a["id"] for a in validate_storyboard(board(assets=[asset(target=""), asset(target=""), {**asset(target=""), "id": "zle"}]))["assets"]]
    assert ids[0] == "a-12345678" and len(set(ids)) == 3


def test_asset_requires_uploaded_image_and_brief_carries_read_path(service):
    with pytest.raises(ValueError, match="není nahraný"):
        service.save(payload(board(assets=[asset(target="kulicka")])))
    service.canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "tex1", "mimeType": "image/png", "dataURL": PNG}})
    assert service.save(payload(board(assets=[asset(target="kulicka")]))) == {"revision": 1}
    section = service.brief_section("draft", "draft", "karta")
    item = section["assets"][0]
    assert item["available"] is True and item["answered"] is False and item["colorUse"] == "tint"
    assert item["read"] == "/api/drawing-files?project=draft&workspace=draft&ids=tex1"
    assert "drawing-file --project draft --workspace draft --id tex1" in item["cli"]
    assert section["workflow"]["openAssets"] == 1 and "Použij 1 podkladů bez odpovědi: „šachovnice“ (texture → kulicka)" in section["workflow"]["next"]
    assert section["layers"] == ["pozadi", "stin", "kulicka"]


def test_asset_instruction_change_reopens_but_agent_answer_holds(service):
    service.canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "tex1", "mimeType": "image/png", "dataURL": PNG}})
    service.save(payload(board(assets=[asset(target="kulicka")])))
    # Agent odpoví: answered true při nezměněném pokynu drží.
    service.save(payload(board(assets=[asset(target="kulicka", answered=True)]), revision=1))
    assert service.read("draft", "draft", "karta")["storyboard"]["assets"][0]["answered"] is True
    # Člověk změní barvu: i se zaškrtnutým answered se podklad znovu otevře.
    service.save(payload(board(assets=[asset(target="kulicka", color="#00ff00", answered=True)]), revision=2))
    assert service.read("draft", "draft", "karta")["storyboard"]["assets"][0]["answered"] is False
    assert service.brief_section("draft", "draft", "karta")["workflow"]["openAssets"] == 1
    # Starší revize = 409, novější vstup člověka zůstane.
    with pytest.raises(ValueError, match="změnil v jiném okně"):
        service.save(payload(board(assets=[asset(target="kulicka", answered=True)]), revision=2))


def test_stale_sketch_without_comment_is_open_work_and_sketch_png_must_exist(service):
    service.save(payload(board(moments=[{"t": 1, "title": "Jen skica"}])))
    moment_id = service.read("draft", "draft", "karta")["storyboard"]["moments"][0]["id"]
    service.mark_sketch_stale("draft", "draft", "karta", moment_id)
    section = service.brief_section("draft", "draft", "karta")
    assert section["workflow"]["openComments"] == 1 and "Jen skica" in section["workflow"]["next"]
    # Agent zareaguje (answered true při nezměněné skice drží); další změna skici člověkem ho zase otevře.
    stored = service.read("draft", "draft", "karta")["storyboard"]
    stored["moments"][0]["answered"] = True
    service.save(payload(stored, revision=stored["revision"]))
    assert service.read("draft", "draft", "karta")["storyboard"]["moments"][0]["answered"] is True
    service.mark_sketch_stale("draft", "draft", "karta", moment_id)
    assert service.read("draft", "draft", "karta")["storyboard"]["moments"][0]["answered"] is False
    with pytest.raises(ValueError, match="PNG skici momentu t=1 s není nahrané"):
        service.save(payload(sketched(), revision=4))


def test_asset_mime_must_match_uploaded_image(service):
    service.canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "tex1", "mimeType": "image/png", "dataURL": PNG}})
    with pytest.raises(ValueError, match="udává image/jpeg, nahraný obrázek je image/png"):
        service.save(payload(board(assets=[asset(target="kulicka", mimeType="image/jpeg")])))


def test_brief_carries_revision_and_saved_time_for_stale_comment_warning(tmp_path):
    from backend.editor.storyboard.storyboard import _workflow

    flow = _workflow([{"t": 0, "comment": "", "annotations": []}], [], "2026-10-16T19:46:49Z", 3)
    assert flow["openComments"] == 0
    assert "19:46:49" in flow["next"] and "revize 3" in flow["next"] and "Uložit" in flow["next"]
    with_comment = _workflow([{"t": 1, "title": "A", "comment": "x", "annotations": [], "answered": False}], [], "2026-10-16T19:46:49Z", 3)
    assert with_comment["openComments"] == 1 and "naposledy" not in with_comment["next"]
