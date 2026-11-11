import pytest

from backend.canvas.canvas_service import CanvasService
from backend.editor.storyboard.storyboard import StoryboardService

MOMENT = "m-3f9a1c2e"
LAYER = f"sb/karta/{MOMENT}"
GRAPH = {"nodes": [{"id": "karta", "parentId": None, "kind": "node", "name": "Karta", "purpose": "", "x": 0, "y": 0}], "edges": []}
SCENE = {"elements": [{"id": "e1", "type": "text", "text": "ahoj", "x": 0, "y": 0, "width": 10, "height": 10}]}


def save(layer, revision=0, scene=SCENE):
    return {"project": "draft", "workspace": "draft", "layer": layer, "expected_revision": revision, "scene": scene}


PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.fixture
def pair(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.save_graph("draft", "draft", GRAPH, canvas.view("draft", "draft")["digest"])
    storyboards = StoryboardService(canvas)
    canvas.sketch_layers_provider = storyboards.sketch_layers
    canvas.sketch_stale_callback = storyboards.mark_sketch_stale
    canvas.drawing_file({"project": "draft", "workspace": "draft", "file": {"id": "f1", "mimeType": "image/png", "dataURL": PNG}})
    board = {"animation": "kulicka", "duration": 12, "moments": [
        {"t": 1, "id": MOMENT, "sketch": {"layer": LAYER, "fileId": "f1"}}]}
    storyboards.save({"project": "draft", "workspace": "draft", "nodeId": "karta", "expected_revision": 0, "storyboard": board})
    return canvas, storyboards


def test_sketch_layer_get_empty_post_and_stale(pair):
    canvas, storyboards = pair
    assert canvas.drawing("draft", "draft", LAYER)["scene"] == {"elements": []}
    saved = canvas.drawing("draft", "draft", LAYER, save(LAYER))
    assert saved["revision"] == 1 and canvas.drawing("draft", "draft", LAYER)["scene"] == SCENE
    stored = storyboards.read("draft", "draft", "karta")
    assert stored["storyboard"]["moments"][0]["sketch"]["imageStale"] is True and stored["revision"] == 2
    assert canvas.drawing("draft", "draft", "karta")["revision"] == 0  # vrstva karty zůstává oddělená


@pytest.mark.parametrize("layer", ["sb/karta/m-ffffffff", "sb/zadna/" + MOMENT, "sb/karta", "sb/karta/zle", "sb/karta/" + MOMENT + "/x"])
def test_foreign_sketch_layer_is_refused(pair, layer):
    canvas, _ = pair
    with pytest.raises(ValueError):
        canvas.drawing("draft", "draft", layer)
    with pytest.raises(ValueError):
        canvas.drawing("draft", "draft", layer, save(layer))


def test_sketch_layer_without_provider_is_refused(pair):
    canvas, _ = pair
    canvas.sketch_layers_provider = None
    with pytest.raises(ValueError, match="Skica momentu neexistuje"):
        canvas.drawing("draft", "draft", LAYER)


def test_agent_creates_sketch_on_moment_without_one(pair):
    canvas, storyboards = pair
    board = storyboards.read("draft", "draft", "karta")
    data = board["storyboard"]
    data["moments"].append({"t": 2, "id": "m-aaaaaaaa"})
    storyboards.save({"project": "draft", "workspace": "draft", "nodeId": "karta", "expected_revision": board["revision"], "storyboard": data})
    layer = "sb/karta/m-aaaaaaaa"
    canvas.drawing("draft", "draft", layer, save(layer))
    moment = storyboards.read("draft", "draft", "karta")["storyboard"]["moments"][1]
    assert moment["sketch"] == {"layer": layer, "fileId": "", "imageStale": True}


SITE_GRAPH = {"nodes": [
    {"id": "app", "parentId": None, "kind": "sector", "name": "Web", "purpose": "", "x": 0, "y": 0,
     "site": {"kind": "application", "environments": []}},
    {"id": "kurz", "parentId": "app", "kind": "node", "name": "Kurz", "purpose": "", "x": 0, "y": 0,
     "site": {"kind": "page", "path": "/kurz", "sections": [{"id": "cta", "role": "cta", "name": "Výzva", "intent": ""}]}},
    {"id": "karta", "parentId": None, "kind": "node", "name": "Karta", "purpose": "", "x": 0, "y": 0}], "edges": []}


def test_box_layer_of_existing_page_section_saves_like_a_sketch(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.save_graph("draft", "draft", SITE_GRAPH, canvas.view("draft", "draft")["digest"])
    layer = "box/kurz/cta"
    assert canvas.drawing("draft", "draft", layer)["revision"] == 0
    assert canvas.drawing("draft", "draft", layer, save(layer))["revision"] == 1
    assert canvas.drawing("draft", "draft", layer)["scene"] == SCENE
    assert canvas.drawing("draft", "draft", "kurz")["revision"] == 0  # vrstva stránky zůstává oddělená
    long_layer = "box/" + "p" * 80 + "/" + "s" * 80  # delší než 80 znaků, přesto tvar vrstvy boxu
    for bad in ("box/kurz/nic", "box/karta/cta", "box/nikdo/cta", "box/kurz", "box/kurz/cta/x", long_layer):
        with pytest.raises(ValueError):
            canvas.drawing("draft", "draft", bad)
        with pytest.raises(ValueError):
            canvas.drawing("draft", "draft", bad, save(bad))
