from backend.wireframe_context import wireframe_context


def test_saved_wireframe_projects_native_geometry_and_frame_relative_coordinates():
    scene = {
        "elements": [
            {"id": "frame", "type": "frame", "x": 100, "y": 200, "width": 400, "height": 300, "name": "Hero", "strokeColor": "#111", "backgroundColor": "#fff", "customData": {"oporaWireframe": {"version": 1, "role": "block", "component": "hero", "notes": "Top", "action": "", "behavior": "", "animation": {"preset": "fade", "durationMs": 200, "delayMs": 0}, "parallax": {"enabled": False, "speed": 0}}}},
            {"id": "title", "type": "text", "x": 120, "y": 230, "width": 80, "height": 20, "text": "Welcome", "frameId": "frame", "strokeColor": "#333", "backgroundColor": "transparent", "customData": {"oporaWireframe": {"version": 1, "role": "element", "component": "heading", "notes": "", "action": "javascript:never()", "behavior": "display", "animation": {"preset": "none", "durationMs": 0, "delayMs": 0}, "parallax": {"enabled": True, "speed": 0.2}}}},
            {"id": "note", "type": "text", "x": 0, "y": 0, "width": 20, "height": 10, "text": "annotation", "strokeColor": "#000", "backgroundColor": "transparent"},
        ]
    }
    result = wireframe_context("p", "draft", "layer", {"scene": scene, "revision": 7, "source": "SQLite"})
    assert result["drawingRevision"] == 7 and result["source"] == "SQLite"
    assert result["blocks"][0]["geometry"] == {"x": 100, "y": 200, "width": 400, "height": 300}
    assert result["blocks"][0]["label"] == "Hero"
    element = result["elements"][0]
    assert element["label"] == "Welcome" and element["frameId"] == "frame"
    assert element["relative"] == {"x": 20, "y": 30, "width": 80, "height": 20}
    assert element["wireframe"]["action"] == "javascript:never()"
    assert result["annotations"][0]["id"] == "note"


def test_context_does_not_infer_frame_relative_coordinates_from_unmarked_frame():
    result = wireframe_context("p", "draft", "", {"scene": {"elements": [
        {"id": "plain", "type": "frame", "x": 2, "y": 3, "width": 40, "height": 40, "strokeColor": "#000", "backgroundColor": "#fff"},
        {"id": "wire", "type": "rectangle", "x": 4, "y": 5, "width": 6, "height": 7, "frameId": "plain", "strokeColor": "#000", "backgroundColor": "#fff", "customData": {"oporaWireframe": {"version": 1, "role": "element", "component": "button", "notes": "", "action": "", "behavior": "", "animation": {"preset": "none", "durationMs": 0, "delayMs": 0}, "parallax": {"enabled": False, "speed": 0}}}},
    ]}, "revision": 0, "source": "SQLite"})
    assert "relative" not in result["elements"][0]
