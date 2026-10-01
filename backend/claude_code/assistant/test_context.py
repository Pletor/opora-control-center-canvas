import json

import pytest

from backend.claude_code.assistant.context import compose, validate_context, validate_text

GOOD = {"projectId": "p1", "workspace": "main", "layerId": None, "selectedNodeIds": ["n1", "n2"],
        "environment": "editor"}


def test_valid_context_and_composition():
    assert validate_context(GOOD) == GOOD
    assert validate_context(None) is None
    text = compose("Co dál?", GOOD)
    assert text.startswith("<opora_context>") and text.endswith("</opora_context>\n\nCo dál?")
    inner = text[len("<opora_context>"):text.index("</opora_context>")]
    assert json.loads(inner) == GOOD
    assert compose("Jen text", None) == "Jen text"


def test_slash_command_stays_first():
    text = compose("/grill-me plán", GOOD)
    assert text.startswith("/grill-me plán\n\n<opora_context>") and text.endswith("</opora_context>")


def test_root_layer_may_be_empty_string():
    assert validate_context({"layerId": ""}) == {"layerId": None}


@pytest.mark.parametrize("bad", [
    "text",
    {"unknown": 1},
    {"projectId": 5},
    {"projectId": "x" * 129},
    {"workspace": ""},
    {"selectedNodeIds": "n1"},
    {"selectedNodeIds": ["n"] * 51},
    {"selectedNodeIds": [1]},
    {"environment": "desktop"},
    {"layerId": "</opora_context>"},
])
def test_invalid_context_is_rejected(bad):
    with pytest.raises(ValueError):
        validate_context(bad)


def test_text_limits():
    assert validate_text("ahoj") == "ahoj"
    for bad in ("", "   ", None, "x" * 20001):
        with pytest.raises(ValueError):
            validate_text(bad)
    assert validate_text("x" * 20000)
