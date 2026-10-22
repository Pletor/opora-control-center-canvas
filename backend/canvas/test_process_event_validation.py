"""Kontrakt opora.process-event/1: výčty, stropy délek, zahození neznámých klíčů."""
import pytest

from backend.canvas.process_event_validation import INGEST_SOURCES, MAX_BATCH, batch, normalize


def event(**overrides):
    base = {"schema": "opora.process-event/1", "id": "office:floor-1:7", "seq": 7, "at": "2026-10-22T10:00:00Z",
            "source": "office", "kind": "tool.use", "phase": "work", "state": "progress", "title": "Edit file",
            "refs": {"project": "draft", "workspace": "draft", "cardId": "a"}}
    return {**base, **overrides}


def test_normalize_keeps_known_keys_and_strips_unknown():
    raw = event(secret="x", refs={"project": "draft", "workspace": "draft", "token": "t", "pr": 12},
                actor={"kind": "worker", "id": "w1", "lease": "zzz"},
                tool={"name": "Edit", "action": "edit", "target": "src/" + "x" * 200, "content": "..."})
    result = normalize(raw)
    assert "secret" not in result
    assert result["refs"] == {"project": "draft", "workspace": "draft", "pr": 12}
    assert result["actor"] == {"kind": "worker", "id": "w1"}
    assert set(result["tool"]) == {"name", "action", "target"}
    assert len(result["tool"]["target"]) == 80 and result["tool"]["target"].endswith("…")


def test_length_caps_clip_title_and_detail():
    result = normalize(event(title="t" * 500, detail="d" * 500))
    assert len(result["title"]) == 120 and len(result["detail"]) == 240


@pytest.mark.parametrize("override", [
    {"schema": "other/1"}, {"phase": "deploy"}, {"state": "done"}, {"source": "mars"}, {"seq": -1},
    {"seq": "1"}, {"at": "včera"}, {"kind": "Bad Kind"}, {"title": " "}, {"refs": None},
    {"actor": {"kind": "robot"}}, {"tool": {"name": "x", "action": "delete"}}, {"refs": {"pr": 0}},
])
def test_invalid_events_are_rejected(override):
    with pytest.raises(ValueError):
        normalize(event(**override))


def test_ingest_sources_exclude_opora():
    with pytest.raises(ValueError):
        normalize(event(source="opora"), sources=INGEST_SOURCES)
    assert normalize(event(source="github"), sources=INGEST_SOURCES)["source"] == "github"


def test_batch_shape():
    assert batch({"events": [1]}) == [1]
    for bad in ({}, {"events": []}, {"events": [1] * (MAX_BATCH + 1)}, {"events": [1], "x": 1}, []):
        with pytest.raises(ValueError):
            batch(bad)
