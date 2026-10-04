import json

import pytest

from backend.claude_code.assistant.context import (
    SCOPE_SELECTION, SCOPE_SELECTION_EMPTY, compose, validate_context, validate_text)

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
    {"scope": "all"},
    {"scope": None},
])
def test_invalid_context_is_rejected(bad):
    with pytest.raises(ValueError):
        validate_context(bad)


def test_text_limits():
    assert validate_text("ahoj") == "ahoj"
    for bad in ("", "   ", None, "x" * 60001):
        with pytest.raises(ValueError):
            validate_text(bad)
    assert validate_text("x" * 60000)


def test_hint_comes_only_from_backend():
    with pytest.raises(ValueError):
        validate_context({**GOOD, "hint": {"sources": ["web"]}})
    hint = {"sources": ["code", "find"], "needsLookup": 0.8}
    text = compose("Kde je login?", GOOD, hint)
    inner = text[len("<opora_context>"):text.index("</opora_context>")]
    assert json.loads(inner) == {**GOOD, "hint": hint}
    assert "</opora_context>\nRelevantní podklad: code, find. Ignoruj, pokud neodpovídá dotazu.\n\nKde je login?" in text
    assert "Relevantní podklad" not in compose("x", None, {"sources": [], "needsLookup": 0.1})
    assert compose("x", GOOD, None) == compose("x", GOOD)


def test_drafts_dir_comes_from_backend_not_ui():
    text = compose("Ahoj", GOOD, drafts_dir="C:/data/assistant-drafts/s1")
    inner = json.loads(text[len("<opora_context>"):text.index("</opora_context>")])
    assert inner["draftsDir"] == "C:/data/assistant-drafts/s1"
    assert compose("Ahoj", None, drafts_dir="D:/x").startswith('<opora_context>{"draftsDir":"D:/x"}</opora_context>')
    with pytest.raises(ValueError):
        validate_context({**GOOD, "draftsDir": "C:/jinam"})


def test_scope_selection_adds_sentence_after_block():
    ctx = {**GOOD, "scope": "selection"}
    assert validate_context(ctx) == ctx
    text = compose("Dodělej to", ctx)
    assert f"</opora_context>\n{SCOPE_SELECTION}\n\nDodělej to" in text
    assert text.startswith("<opora_context>")


def test_scope_selection_without_selection_asks():
    for ctx in ({**GOOD, "selectedNodeIds": [], "scope": "selection"}, {"scope": "selection"}):
        assert compose("x", ctx).endswith(f"</opora_context>\n{SCOPE_SELECTION_EMPTY}\n\nx")


def test_scope_board_or_missing_adds_nothing():
    assert "Rozsah:" not in compose("x", {**GOOD, "scope": "board"})
    assert "Rozsah:" not in compose("x", GOOD)
    assert validate_context({"scope": "board"}) == {"scope": "board"}


def test_scope_sentence_with_slash_command():
    text = compose("/grill-me", {**GOOD, "scope": "selection"})
    assert text.startswith("/grill-me\n\n<opora_context>") and text.endswith(SCOPE_SELECTION)
