"""Podněty k dalšímu vývoji: tvar, limity, přidání bez duplicit a souhrn pro node-brief."""
import pytest

from backend.editor.agent_memory.card_ideas import (
    MAX_IDEA_TEXT,
    MAX_IDEAS,
    MAX_OUTPUT_IDEAS,
    brief_of,
    merge_ideas,
    validate_ideas,
    validate_output_ideas,
)


def idea(iid, text="Zalomit dlouhý název.", **overrides):
    item = {"id": iid, "text": text, "by": "critic-1", "source": "critic:sly", "at": "2026-10-09T10:00:00+00:00",
            "status": "open"}
    item.update(overrides)
    return item


def test_valid_ideas_and_rejected_shapes():
    validate_ideas([idea("a"), idea("b", stageId="s1", status="done", source="human")])
    for broken in ([idea("a"), idea("a")], [idea("a", status="later")], [idea("a", source="boss")],
                   [idea("a", text=" ")], [idea("a", text="x" * (MAX_IDEA_TEXT + 1))], [{**idea("a"), "extra": 1}],
                   [idea("a", stageId="../x")], [idea(str(n)) for n in range(MAX_IDEAS + 1)]):
        with pytest.raises(ValueError):
            validate_ideas(broken)


def test_output_ideas_have_text_and_source_and_a_count_limit():
    validate_output_ideas([{"text": "Nápověda u pole.", "source": "review"}])
    for broken in ([{"text": "x"}], [{"text": "", "source": "review"}], [{"text": "x", "source": "critic:boss"}],
                   [{"text": "x", "source": "review"}] * (MAX_OUTPUT_IDEAS + 1)):
        with pytest.raises(ValueError):
            validate_output_ideas(broken)


def test_merge_skips_duplicates_by_text_and_keeps_existing():
    existing = [idea("a", status="done")]
    merged = merge_ideas(existing, [{"text": "  zalomit DLOUHÝ   název. ", "source": "review"},
                                    {"text": "Nový podnět", "source": "critic:user"},
                                    {"text": "nový podnět", "source": "critic:sly"}], "kritik-2", "T", "s1")
    assert [item["text"] for item in merged] == ["Zalomit dlouhý název.", "Nový podnět"]
    assert merged[0]["status"] == "done" and merged[1]["stageId"] == "s1" and merged[1]["by"] == "kritik-2"
    validate_ideas(merged)
    with pytest.raises(ValueError):
        merge_ideas([idea(str(n), text=f"p{n}") for n in range(MAX_IDEAS)], [{"text": "navíc", "source": "review"}], "a", "T")


def test_brief_lists_open_ideas_and_counts_done():
    summary = brief_of([idea("a"), idea("b", text="Hotovo", status="done")])
    assert [item["id"] for item in summary["open"]] == ["a"] and summary["done"] == 1
    assert brief_of(None)["open"] == []


def test_fragment_id_is_optional_validated_and_carried_from_output():
    validate_ideas([idea("a", fragmentId="f1"), idea("b", stageId="s1", fragmentId="f2")])
    for broken in ([idea("a", fragmentId="../x")], [idea("a", fragmentId=7)]):
        with pytest.raises(ValueError):
            validate_ideas(broken)
    validate_output_ideas([{"text": "K fragmentu.", "source": "review", "fragmentId": "f1"}])
    with pytest.raises(ValueError):
        validate_output_ideas([{"text": "K fragmentu.", "source": "review", "fragmentId": "a/b"}])
    merged = merge_ideas([], [{"text": "K fragmentu.", "source": "review", "fragmentId": "f1"}], "a", "T")
    assert merged[0]["fragmentId"] == "f1" and brief_of(merged)["open"][0]["fragmentId"] == "f1"
